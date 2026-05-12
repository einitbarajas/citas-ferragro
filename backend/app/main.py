import asyncio
import logging
import re
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

from app.api import admin, appointments, auth, crud
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.responses import error_response, ok_response
from app.db.base import Base
from app.db.session import engine
from app.services.reminder_scheduler import reminder_scheduler_loop

import app.models  # noqa: F401 — registra tablas en Base.metadata antes de create_all

logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

SUSPICIOUS_QUERY_PATTERNS = [
    re.compile(r"(?i)(?:')\s*or\s*(?:'?\d+'?\s*=\s*'?\d+'?|true)"),
    re.compile(r"(?i)\bunion\b\s+(?:all\s+)?\bselect\b"),
    re.compile(r"(?i)(?:--|/\*|\*/|;)\s*(?:select|insert|update|delete|drop|alter|create|truncate)\b"),
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = asyncio.Event()
    scheduler_task = asyncio.create_task(reminder_scheduler_loop(stop_event))
    yield
    stop_event.set()
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=_cors_lan_regex if (settings.cors_allow_private_network and not settings.is_production) else None,
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
                hdrs.pop("cross-origin-opener-policy", None)
                hdrs.pop("cross-origin-resource-policy", None)
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
    app.include_router(admin.router, prefix=api_prefix)

# Último add_middleware: primero en la lista de usuario → capa exterior que intercepta `send`.
app.add_middleware(PatchOpenApiDocsCspMiddleware)

CONSTRAINT_ERROR_MESSAGES = {
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
def data_exception_handler(_, __):
    return JSONResponse(
        status_code=400,
        content=error_response("El formato o tamaño de uno o más campos es inválido."),
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


@app.get("/health")
def health():
    return ok_response({"status": "ok"}, "Servicio activo")


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
