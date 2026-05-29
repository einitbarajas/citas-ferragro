import os
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.smtp_env_loader import bootstrap_smtp_from_secret_files

bootstrap_smtp_from_secret_files()


def _resolve_env_files() -> tuple[str, ...]:
    """Local .env + secret files de Render (/etc/secrets) para SMTP en producción."""
    backend_dir = Path(__file__).resolve().parents[2]
    repo_root = backend_dir.parent
    candidates = [
        repo_root / ".env",
        Path("/etc/secrets/smtp.env"),
        Path("/etc/secrets/.env"),
        backend_dir / "smtp.env",
    ]
    paths: list[str] = []
    seen: set[str] = set()
    for path in candidates:
        if not path.is_file():
            continue
        key = str(path.resolve())
        if key in seen:
            continue
        paths.append(key)
        seen.add(key)
    if not paths:
        paths.append(str(repo_root / ".env"))
    return tuple(paths)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_resolve_env_files(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15
    forgot_password_cooldown_seconds: int = 60
    # Horas mínimas entre el momento de agendar/reprogramar y el inicio de la cita (proveedor).
    appointment_minimum_notice_hours: int = 24
    # Horas mínimas antes del inicio para cancelar una cita (proveedor y staff sin exención).
    appointment_cancel_minimum_notice_hours: int = 12
    # Máximo de equipos de descarga en paralelo (bodega o proveedor).
    max_unload_teams: int = 20
    reminder_scheduler_interval_seconds: int = 300
    # Retención de notificaciones (días) para evitar saturación en UI.
    notification_retention_days: int = 30
    # Intervalo del scheduler de purga de notificaciones (segundos).
    notification_purge_interval_seconds: int = 3600
    # Intervalo del scheduler que marca no presentada tras 15 min en citas revisadas.
    no_presentada_scheduler_interval_seconds: int = 60
    # Minutos tras start_time para auto marcar no presentada si sigue en revisado.
    appointment_finalization_grace_minutes: int = 15
    # Proveedores suspendidos: días hasta purga automática (credenciales, citas, etc.; conserva AuditoriaSistema).
    provider_purge_after_days: int = 180
    provider_purge_check_interval_seconds: int = 3600
    rate_limit_per_minute_default: int = 120
    rate_limit_per_minute_auth: int = 20
    # Desactivar (false) solo en entornos de carga/pruebas de estrés; en producción debe quedar activo.
    rate_limit_enabled: bool = True
    refresh_cookie_name: str = "refresh_token"
    refresh_cookie_secure: bool = False
    refresh_cookie_samesite: str = "lax"
    cors_origins: str = "http://localhost:2711,http://127.0.0.1:2711"
    # Si es true, permite orígenes http en localhost y redes privadas (192.168.x, 10.x) en cualquier puerto (Vite, etc.).
    cors_allow_private_network: bool = False
    # Hora local usada para validar que el inicio de la cita caiga en una franja permitida.
    business_timezone: str = "America/Bogota"
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""
    cloudinary_folder: str = "ferragro/perfiles"
    # Perfil SMTP opcional: office365 | gmail (rellena host/puerto si SMTP_HOST está vacío).
    smtp_profile: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "Ferragro"
    smtp_use_tls: bool = True
    # true = conexión SSL directa (puerto 465, p. ej. algunos Gmail); false = STARTTLS (587).
    smtp_use_ssl: bool = False
    smtp_reply_to: str = ""
    # Solo para emergencias: POST /auth/maintenance/reset-admin-password con header X-Maintenance-Token.
    # Déjalo vacío en producción normal; quítalo tras usarlo.
    maintenance_token: str = ""
    # Producción: al arrancar el API, asegura Admin documento 90000001 (correo/clave válidos, sin bloqueo).
    admin_bootstrap_enabled: bool = True
    admin_bootstrap_email: str = "ebarajas@ferragro.com"
    admin_bootstrap_password: str = "FerragroPortal2026!"

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host.strip() and self.smtp_from_email.strip())

    @property
    def smtp_send_ready(self) -> bool:
        return bool(
            self.smtp_configured
            and self.smtp_user.strip()
            and self.smtp_password.strip()
        )

    @model_validator(mode="after")
    def apply_smtp_profile_defaults(self) -> "Settings":
        _apply_smtp_profile_defaults(self)
        from app.services.smtp_settings import finalize_smtp_settings

        finalize_smtp_settings(self)
        return self

    @model_validator(mode="after")
    def apply_production_defaults(self) -> "Settings":
        if not self.is_production:
            return self
        if not self.refresh_cookie_secure:
            object.__setattr__(self, "refresh_cookie_secure", True)
        if self.refresh_cookie_samesite.lower() in {"", "lax"}:
            object.__setattr__(self, "refresh_cookie_samesite", "none")
        return self


def _apply_smtp_profile_defaults(target: Settings) -> None:
    profile = target.smtp_profile.strip().lower()
    presets: dict[str, dict[str, object]] = {
        "office365": {
            "host": "smtp.office365.com",
            "port": 587,
            "use_tls": True,
            "use_ssl": False,
        },
        "outlook": {
            "host": "smtp.office365.com",
            "port": 587,
            "use_tls": True,
            "use_ssl": False,
        },
        "gmail": {
            "host": "smtp.gmail.com",
            "port": 587,
            "use_tls": True,
            "use_ssl": False,
        },
        "gmail_ssl": {
            "host": "smtp.gmail.com",
            "port": 465,
            "use_tls": False,
            "use_ssl": True,
        },
    }
    if profile in presets and not target.smtp_host.strip():
        preset = presets[profile]
        object.__setattr__(target, "smtp_host", str(preset["host"]))
        object.__setattr__(target, "smtp_port", int(preset["port"]))
        object.__setattr__(target, "smtp_use_tls", bool(preset["use_tls"]))
        object.__setattr__(target, "smtp_use_ssl", bool(preset["use_ssl"]))


settings = Settings()

_SMTP_ENV_KEYS: tuple[tuple[str, str, type], ...] = (
    ("smtp_profile", "SMTP_PROFILE", str),
    ("smtp_host", "SMTP_HOST", str),
    ("smtp_port", "SMTP_PORT", int),
    ("smtp_user", "SMTP_USER", str),
    ("smtp_password", "SMTP_PASSWORD", str),
    ("smtp_from_email", "SMTP_FROM_EMAIL", str),
    ("smtp_from_name", "SMTP_FROM_NAME", str),
    ("smtp_reply_to", "SMTP_REPLY_TO", str),
)


def _coerce_env_value(raw: str, target_type: type):
    if target_type is bool:
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    if target_type is int:
        return int(raw.strip())
    return raw.strip()


def refresh_smtp_settings() -> bool:
    """
    Relee SMTP desde variables de entorno y archivos secretos de Render.
    Útil si el proceso arrancó antes de montar /etc/secrets o las vars se añadieron después.
    """
    applied = bootstrap_smtp_from_secret_files()
    for attr, env_key, target_type in _SMTP_ENV_KEYS:
        raw = os.getenv(env_key)
        if raw is None or not str(raw).strip():
            continue
        object.__setattr__(settings, attr, _coerce_env_value(str(raw), target_type))
    tls = os.getenv("SMTP_USE_TLS")
    if tls is not None and str(tls).strip():
        object.__setattr__(settings, "smtp_use_tls", _coerce_env_value(str(tls), bool))
    ssl = os.getenv("SMTP_USE_SSL")
    if ssl is not None and str(ssl).strip():
        object.__setattr__(settings, "smtp_use_ssl", _coerce_env_value(str(ssl), bool))
    _apply_smtp_profile_defaults(settings)
    from app.services.smtp_settings import finalize_smtp_settings

    finalize_smtp_settings(settings)
    if applied:
        import logging

        logging.getLogger(__name__).info("SMTP cargado desde archivos: %s", ", ".join(applied))
    return settings.smtp_send_ready
