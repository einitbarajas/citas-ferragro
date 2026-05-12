from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Credential(Base):
    __tablename__ = "Credenciales"

    id: Mapped[int] = mapped_column("IdCredencial", primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column("Correo", String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column("HashContrasena", String(255), nullable=False)

    user = relationship("User", back_populates="credential", uselist=False)
    provider = relationship("Provider", back_populates="credential", uselist=False)
    profile_photo = relationship("ProfilePhoto", back_populates="credential", uselist=False)
    refresh_sessions = relationship("RefreshSession", back_populates="credential", cascade="all, delete-orphan")
    login_attempt = relationship("LoginAttempt", back_populates="credential", uselist=False)
    login_audits = relationship("LoginAudit", back_populates="credential")
    password_reset_state = relationship(
        "PasswordResetState",
        back_populates="credential",
        uselist=False,
        cascade="all, delete-orphan",
    )
