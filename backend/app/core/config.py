from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
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
    reminder_scheduler_interval_seconds: int = 300
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
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "Ferragro"
    smtp_use_tls: bool = True

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @model_validator(mode="after")
    def apply_production_defaults(self) -> "Settings":
        if not self.is_production:
            return self
        if not self.refresh_cookie_secure:
            object.__setattr__(self, "refresh_cookie_secure", True)
        if self.refresh_cookie_samesite.lower() in {"", "lax"}:
            object.__setattr__(self, "refresh_cookie_samesite", "none")
        return self


settings = Settings()
