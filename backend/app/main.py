import asyncio
import logging
import os
import re
import time
import uuid
from contextlib import asynccontextmanager

import uvicorn
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi import HTTPException
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from sqlalchemy.exc import DataError, IntegrityError, SQLAlchemyError

from app.api import admin, appointments, auth, crud, notifications
from app.core.config import refresh_smtp_settings, settings
from app.core.rate_limit import limiter
from app.core.responses import error_response, ok_response
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.services.admin_bootstrap import ensure_production_admin
from app.services.credential_cleanup import purge_orphan_credentials
from app.services.provider_purge_scheduler import provider_purge_scheduler_loop
from app.services.email_dispatch import shutdown_email_executor
from app.services.no_presentada_scheduler import no_presentada_scheduler_loop
from app.services.reminder_scheduler import reminder_scheduler_loop
from app.services.notification_purge_scheduler import notification_purge_scheduler_loop

# Production deploy marker (health build_id below).
API_BUILD_ID = "2026-05-29-smtp-email-v3"

import app.models  # noqa: F401 — registra tablas en Base.metadata

logger = logging.getLogger(__name__)


def _init_database_schema(*, max_attempts: int = 6, delay_seconds: float = 5.0) -> None:
    """
    Sincroniza tablas al arranque (no en import: Render health check necesita que uvicorn suba rápido).
    Reintenta: la BD interna a veces no acepta conexiones en los primeros segundos del deploy.
    """
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            Base.metadata.create_all(bind=engine)
            if attempt > 1:
                logger.info("Esquema BD listo en intento %s/%s", attempt, max_attempts)
            return
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Esquema BD: intento %s/%s falló (%s: %s)",
                attempt,
                max_attempts,
                type(exc).__name__,
                exc,
            )
            if attempt < max_attempts:
                time.sleep(delay_seconds)
    logger.error(
        "No se pudo conectar a PostgreSQL tras %s intentos. "
        "Revisa en Render que ferragro-api tenga DATABASE_URL del Postgres vinculado.",
        max_attempts,
    )

SUSPICIOUS_QUERY_PATTERNS = [
    re.compile(r"(?i)(?:')\s*or\s*(?:'?\d+'?\s*=\s*'?\d+'?|true)"),
    re.compile(r"(?i)\bunion\b\s+(?:all\s+)?\bselect\b"),
    re.compile(r"(?i)(?:--|/\*|\*/|;)\s*(?:select|insert|update|delete|drop|alter|create|truncate)\b"),
]


def _warn_if_smtp_missing_in_production() -> None:
    refresh_smtp_settings()
    if settings.is_production and not settings.smtp_configured:
        logger.warning(
            "SMTP no configurado en producción (SMTP_HOST / SMTP_FROM_EMAIL). "
            "Los correos de bienvenida, recuperación de contraseña y avisos de citas "
            "no se enviarán; solo quedarán en los logs del servicio."
        )


def _purge_orphan_credentials_on_startup() -> None:
    if not settings.is_production:
        return
    try:
        with SessionLocal() as db:
            removed = purge_orphan_credentials(db)
            if removed:
                db.commit()
                logger.info("Credenciales huérfanas eliminadas al arranque: %s", removed)
    except Exception:
        logger.exception("No se pudo limpiar credenciales huérfanas al arranque")


def _ensure_production_admin_on_startup() -> None:
    if not settings.is_production or not settings.admin_bootstrap_enabled:
        return
    try:
        with SessionLocal() as db:
            purge_orphan_credentials(db)
            ensure_production_admin(db)
            db.commit()
            logger.info("Admin de producción verificado al arranque")
    except Exception:
        logger.exception("No se pudo asegurar el Admin de producción al arranque")


def _log_database_target() -> None:
    try:
        from urllib.parse import urlparse

        raw = settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        parsed = urlparse(raw)
        logger.info(
            "PostgreSQL: host=%s port=%s db=%s",
            parsed.hostname or "?",
            parsed.port or "5432",
            (parsed.path or "/").lstrip("/") or "?",
        )
    except Exception:
        logger.warning("No se pudo parsear DATABASE_URL para diagnóstico")


def _warm_smtp_on_startup() -> None:
    if not settings.is_production:
        return
    try:
        from app.core.config import refresh_smtp_settings
        from app.core.smtp_env_loader import overlay_render_smtp_secret
        from app.services.email_transport import email_delivery_ready, render_smtp_blocked
        from app.services.smtp_resolver import ensure_smtp_login_ready, resolved_smtp_label

        overlay_render_smtp_secret()
        refresh_smtp_settings()
        if settings.resend_send_ready:
            logger.info(
                "Correo en producción vía Resend (sandbox=%s)",
                settings.resend_sandbox,
            )
            return
        if settings.brevo_send_ready:
            logger.info("Correo en producción vía Brevo API")
            return
        if settings.smtp_send_ready and not render_smtp_blocked():
            if ensure_smtp_login_ready():
                logger.info("SMTP Gmail listo al arranque (%s)", resolved_smtp_label())
            else:
                logger.warning("SMTP configurado pero login falló; revisa smtp.env")
        elif settings.smtp_send_ready:
            logger.warning(
                "Render bloquea SMTP (587/465). Añade RESEND_API_KEY en Environment o sube a plan Starter."
            )
        elif not email_delivery_ready():
            logger.warning("Correo no configurado en producción")
    except Exception:
        logger.exception("Fallo al validar correo al arranque")


def _blocking_startup() -> None:
    """Tareas síncronas de BD (se ejecutan en hilo aparte; no bloquean /health de Render)."""
    _log_database_target()
    _init_database_schema(max_attempts=12, delay_seconds=3.0)
    _purge_orphan_credentials_on_startup()
    _ensure_production_admin_on_startup()
    _warm_smtp_on_startup()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _warn_if_smtp_missing_in_production()
    stop_event = asyncio.Event()

    async def _background_startup() -> None:
        try:
            await asyncio.to_thread(_blocking_startup)
            logger.info("Arranque en segundo plano: BD y admin listos")
        except Exception:
            logger.exception("Arranque en segundo plano falló (revisa DATABASE_URL en Render)")

    startup_task = asyncio.create_task(_background_startup())
    scheduler_task = asyncio.create_task(reminder_scheduler_loop(stop_event))
    purge_task = asyncio.create_task(provider_purge_scheduler_loop(stop_event))
    no_presentada_task = asyncio.create_task(no_presentada_scheduler_loop(stop_event))
    notification_purge_task = asyncio.create_task(notification_purge_scheduler_loop(stop_event))
    # Render health check: /health debe responder en cuanto uvicorn acepta conexiones.
    yield
    stop_event.set()
    if not startup_task.done():
        startup_task.cancel()
        try:
            await startup_task
        except asyncio.CancelledError:
            pass
    scheduler_task.cancel()
    purge_task.cancel()
    no_presentada_task.cancel()
    notification_purge_task.cancel()
    for task in (scheduler_task, purge_task, no_presentada_task, notification_purge_task):
        try:
            await task
        except asyncio.CancelledError:
            pass
    shutdown_email_executor()


app = FastAPI(
    title="Ferragro Appointments API",
    description="API para gestionar roles, usuarios, proveedores, citas e historial.",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    cid = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = cid
    return response


def _is_suspicious_query_value(value: str) -> bool:
    if not value:
        return False
    normalized = value.strip()
    return any(pattern.search(normalized) for pattern in SUSPICIOUS_QUERY_PATTERNS)


@app.middleware("http")
async def reject_suspicious_query_params(request: Request, call_next):
    suspicious_params = [
        key
        for key, value in request.query_params.multi_items()
        if _is_suspicious_query_value(value)
    ]
    if suspicious_params:
        return JSONResponse(
            status_code=400,
            content=error_response(
                "Parámetros de URL inválidos o potencialmente peligrosos.",
                data={"suspicious_params": sorted(set(suspicious_params))},
            ),
        )
    return await call_next(request)


origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]

# Origenes típicos al abrir el frontend por IP de LAN (p. ej. http://192.168.3.60:2711).
_cors_lan_regex = (
    r"^http://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3})(:\d+)?$"
)
# Producción: dominios Vercel del equipo ferragro (citas.ferragro, frontend-ferragro, previews).
_cors_vercel_ferragro_regex = r"^https://(?:[a-z0-9-]+\.ferragro|[a-z0-9-]+-ferragro)\.vercel\.app$"

if settings.cors_allow_private_network and not settings.is_production:
    _cors_origin_regex = _cors_lan_regex
elif settings.is_production:
    _cors_origin_regex = _cors_vercel_ferragro_regex
else:
    _cors_origin_regex = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=_cors_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Correlation-ID"],
)


def _http_path_from_scope(scope: Scope) -> str:
    """Ruta HTTP normalizada (incl. root_path si el app está montado)."""
    root = scope.get("root_path") or ""
    if isinstance(root, bytes):
        root = root.decode("latin-1")
    raw = scope.get("path") or scope.get("raw_path") or "/"
    if isinstance(raw, bytes):
        raw = raw.decode("latin-1")
    combined = f"{root}{raw}".split("?", 1)[0].strip() or "/"
    return combined


def _is_openapi_doc_path(path: str) -> bool:
    """Rutas de Swagger/ReDoc/OpenAPI."""
    p = path.rstrip("/") or "/"
    if p in ("/openapi.json", "/openapi.yaml"):
        return True
    if p == "/docs" or p.startswith("/docs/"):
        return True
    if p == "/redoc" or p.startswith("/redoc/"):
        return True
    # Coincidencias laxas (algunos proxies / montajes)
    if "openapi.json" in p or p.endswith("openapi.json"):
        return True
    return False


# Swagger UI 5: jsdelivr + scripts inline; a veces eval en presets.
_DOC_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: blob: https://cdn.jsdelivr.net https://fastapi.tiangolo.com; "
    "font-src 'self' data: https://cdn.jsdelivr.net; "
    "connect-src 'self' http://127.0.0.1:8000 http://localhost:8000 ws://127.0.0.1:8000 ws://localhost:8000; "
    "worker-src 'self' blob:; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


class PatchOpenApiDocsCspMiddleware:
    """
    En producción: reescribe la CSP en `http.response.start` para /docs y OpenAPI
    (la CSP estricta bloquea el CDN de Swagger). En desarrollo no se usa.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = _http_path_from_scope(scope)
        doc = _is_openapi_doc_path(path.rstrip("/") or "/")

        # En desarrollo no aplicamos CSP estricta: no hace falta interceptar `send`.
        if not doc or not settings.is_production:
            await self.app(scope, receive, send)
            return

        async def send_patch(message: Message) -> None:
            if message["type"] == "http.response.start":
                hdrs = MutableHeaders(raw=list(message.get("headers") or []))
                hdrs["content-security-policy"] = _DOC_CSP
                for _hop in ("cross-origin-opener-policy", "cross-origin-resource-policy"):
                    if _hop in hdrs:
                        del hdrs[_hop]
                message = {**message, "headers": hdrs.raw}
            await send(message)

        await self.app(scope, receive, send_patch)


@app.middleware("http")
async def set_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    # CSP estricta rompe Swagger (CDN + inline). En desarrollo no la enviamos; en producción sí + parche ASGI en /docs.
    if settings.is_production:
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-site"
        csp = (
            "default-src 'self'; "
            "img-src 'self' data: https://res.cloudinary.com; "
            "style-src 'self'; "
            "script-src 'self'; "
            "connect-src 'self' http://localhost:2711 http://127.0.0.1:2711; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        response.headers["Content-Security-Policy"] = csp
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


for api_prefix in ("/api", "/api/v1"):
    app.include_router(auth.router, prefix=api_prefix)
    app.include_router(crud.router, prefix=api_prefix)
    app.include_router(appointments.router, prefix=api_prefix)
    app.include_router(notifications.router, prefix=api_prefix)
    app.include_router(admin.router, prefix=api_prefix)

# Último add_middleware: primero en la lista de usuario → capa exterior que intercepta `send`.
app.add_middleware(PatchOpenApiDocsCspMiddleware)

CONSTRAINT_ERROR_MESSAGES = {
    "UqFranjaFechaBodegaOrden": (
        "Ya hay una franja con ese orden para este día y bodega. "
        "Elige otro equipo de descarga o cambia el orden del turno."
    ),
    "UqFranjaFechaBodegaOrdenCompartido": (
        "Ya existe una franja compartida con ese orden para este día. Añade otro turno u otro equipo."
    ),
    "UqFranjaFechaBodegaEquipoOrden": (
        "Ya existe una franja para ese muelle con el mismo orden en este día."
    ),
    "UqFranjaBodegaOrden": (
        "Ya hay una franja semanal con ese orden para esta bodega. Elige otro equipo u otro turno."
    ),
    "UqFranjaBodegaOrdenCompartido": (
        "Ya existe una franja semanal compartida con ese orden. Añade otro turno u otro equipo."
    ),
    "UqFranjaBodegaEquipoOrden": (
        "Ya existe una franja semanal para ese muelle con el mismo orden."
    ),
    "Credenciales_Correo_key": "El correo ya está registrado.",
    "Usuarios_IdCredencial_key": "Las credenciales del usuario ya están asociadas a otra cuenta.",
    "Proveedores_IdCredencial_key": "Las credenciales del proveedor ya están asociadas a otra cuenta.",
    "ChkUsuariosIdDocumentoPorRol": "El documento debe contener entre 7 y 10 dígitos.",
    "ChkProveedoresDocumentoPersonaResponsable": "El documento de la persona responsable debe contener entre 7 y 10 dígitos.",
    "ChkProveedoresDigitoVerificacion": "El dígito de verificación debe ser un número de un solo dígito.",
}


def _extract_constraint_name(exc: IntegrityError) -> str | None:
    original = getattr(exc, "orig", None)
    if not original:
        return None

    diag = getattr(original, "diag", None)
    if diag and getattr(diag, "constraint_name", None):
        return diag.constraint_name

    message = str(original)
    match = re.search(r'constraint "([^"]+)"', message)
    if match:
        return match.group(1)
    return None


def _extract_not_null_column(exc: IntegrityError) -> str | None:
    original = getattr(exc, "orig", None)
    if not original:
        return None

    diag = getattr(original, "diag", None)
    if diag and getattr(diag, "column_name", None):
        return diag.column_name
    return None


@app.exception_handler(HTTPException)
def http_exception_handler(_, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(str(exc.detail)),
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
def validation_exception_handler(_, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=error_response("Error de validación", data=exc.errors()),
    )


@app.exception_handler(IntegrityError)
def integrity_exception_handler(_, exc: IntegrityError):
    constraint_name = _extract_constraint_name(exc)
    if constraint_name and constraint_name in CONSTRAINT_ERROR_MESSAGES:
        return JSONResponse(
            status_code=400,
            content=error_response(CONSTRAINT_ERROR_MESSAGES[constraint_name]),
        )

    original = str(getattr(exc, "orig", "")).lower()

    if "unique" in original or "duplicate key" in original:
        message = "Ya existe un registro con ese valor."
    elif "foreign key" in original:
        message = "La referencia indicada no existe o no es válida."
    elif "not-null" in original or "null value" in original:
        column = _extract_not_null_column(exc)
        if column:
            message = f"El campo '{column}' es obligatorio."
        else:
            message = "Faltan datos obligatorios para completar la operación."
    else:
        message = "No se pudo guardar la información por una restricción de datos."

    return JSONResponse(
        status_code=400,
        content=error_response(message),
    )


@app.exception_handler(DataError)
def data_exception_handler(_, exc: DataError):
    original = str(getattr(exc, "orig", exc) or "").lower()
    if "out of range" in original or "fuera de rango" in original:
        message = (
            "Un valor numérico supera el tamaño permitido en la base de datos. "
            "Si reprogramaste o actualizaste una cita, revisa que el NIT del proveedor sea válido."
        )
    elif "invalid input syntax" in original or "sintaxis de entrada no es válida" in original:
        message = "El formato de fecha, hora o número enviado no es válido."
    elif "value too long" in original or "demasiado largo" in original:
        message = "Uno de los campos supera la longitud máxima permitida."
    else:
        message = "El formato o tamaño de uno o más campos es inválido."

    return JSONResponse(
        status_code=400,
        content=error_response(message),
    )


@app.exception_handler(SQLAlchemyError)
def sqlalchemy_exception_handler(_, __):
    return JSONResponse(
        status_code=500,
        content=error_response("Error de base de datos"),
    )


@app.exception_handler(Exception)
def unhandled_exception_handler(_, __):
    return JSONResponse(
        status_code=500,
        content=error_response("Error interno del servidor"),
    )


@app.get("/")
def root():
    """Raíz pública: versión desplegada (Render health check y navegador)."""
    return ok_response(
        {
            "service": "ferragro-api",
            "build_id": API_BUILD_ID,
            "render_git_commit": os.getenv("RENDER_GIT_COMMIT"),
            "docs": "/docs",
            "health": "/health",
        },
        "Ferragro Appointments API",
    )


@app.get("/health")
def health():
    # Respuesta rápida para health check de Render (sin BD ni SMTP en cada ping).
    refresh_smtp_settings()
    from app.services.email_transport import email_delivery_ready, render_smtp_blocked

    smtp_blocked = settings.is_production and render_smtp_blocked()
    can_deliver = email_delivery_ready()
    return ok_response(
        {
            "status": "ok",
            "build_id": API_BUILD_ID,
            "render_git_commit": os.getenv("RENDER_GIT_COMMIT"),
            "email_enabled": can_deliver,
            "email_configured": settings.email_send_ready,
            "email_provider": settings.email_provider,
            "resend_ready": settings.resend_send_ready,
            "resend_sandbox": settings.resend_sandbox,
            "brevo_ready": settings.brevo_send_ready,
            "smtp_send_ready": settings.smtp_send_ready,
            "smtp_blocked_on_host": smtp_blocked if settings.is_production else None,
            "smtp_host": settings.smtp_host or None,
            "render_smtp_blocked_hint": (
                "Render free bloquea SMTP; configura RESEND_API_KEY (y RESEND_SANDBOX=true) o BREVO_API_KEY."
                if settings.is_production and smtp_blocked and not can_deliver
                else None
            ),
            "smtp_diag": {
                "host_set": bool(settings.smtp_host.strip()),
                "user_set": bool(settings.smtp_user.strip()),
                "password_set": bool(settings.smtp_password.strip()),
                "from_email_set": bool(settings.smtp_from_email.strip()),
                "user_matches_from": (
                    (settings.smtp_user or "").strip().lower()
                    == (settings.smtp_from_email or "").strip().lower()
                ),
            },
        },
        "Servicio activo",
    )


@app.get("/health/deep")
def health_deep():
    """Diagnóstico manual: BD + admin bootstrap (no usar como health check de Render)."""
    admin_email: str | None = None
    db_ok = False
    try:
        from sqlalchemy import select, text

        from app.models.user import User

        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            db_ok = True
            user = db.execute(select(User).where(User.document_id == "90000001")).scalar_one_or_none()
            if user and user.credential:
                admin_email = user.credential.email
    except Exception:
        logger.exception("health/deep: fallo de BD")
    from app.core.smtp_env_loader import overlay_render_smtp_secret
    from app.services.email_transport import email_delivery_ready

    overlay_render_smtp_secret()
    smtp_ok = refresh_smtp_settings()
    smtp_login_ok: bool | None = None
    smtp_profile_label: str | None = None
    if settings.brevo_send_ready:
        smtp_login_ok = True
        smtp_profile_label = "brevo_https"
    elif settings.resend_send_ready:
        smtp_login_ok = True
        smtp_profile_label = "resend_https" + ("_sandbox" if settings.resend_sandbox else "")
    elif settings.smtp_send_ready:
        from app.services.mailer import smtp_login_probe_with_timeout
        from app.services.smtp_resolver import resolved_smtp_label

        smtp_login_ok = smtp_login_probe_with_timeout(40.0)
        smtp_profile_label = resolved_smtp_label()
    return ok_response(
        {
            "status": "ok"
            if db_ok
            and (smtp_login_ok is True or settings.brevo_send_ready or settings.resend_send_ready)
            else "degraded",
            "build_id": API_BUILD_ID,
            "render_git_commit": os.getenv("RENDER_GIT_COMMIT"),
            "database_ok": db_ok,
            "email_enabled": email_delivery_ready(),
            "email_configured": settings.email_send_ready,
            "email_provider": settings.email_provider,
            "resend_ready": settings.resend_send_ready,
            "brevo_ready": settings.brevo_send_ready,
            "smtp_send_ready": settings.smtp_send_ready,
            "smtp_login_ok": smtp_login_ok if settings.smtp_send_ready else None,
            "smtp_profile": smtp_profile_label,
            "admin_email": admin_email,
        },
        "Diagnóstico profundo",
    )


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
