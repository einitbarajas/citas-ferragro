from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LoginAudit(Base):
    __tablename__ = "AuditoriaLogin"

    id: Mapped[int] = mapped_column("Id", primary_key=True, autoincrement=True)
    credential_id: Mapped[int | None] = mapped_column(
        "IdCredencial", ForeignKey("Credenciales.IdCredencial", ondelete="SET NULL"), nullable=True
    )
    email: Mapped[str] = mapped_column("Correo", String(255), nullable=False, index=True)
    success: Mapped[bool] = mapped_column("Exito", Boolean, nullable=False)
    ip_address: Mapped[str | None] = mapped_column("DireccionIp", String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column("UserAgent", Text, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column("MotivoFallo", String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column("CreadoEn", DateTime(timezone=True), nullable=False)

    credential = relationship("Credential", back_populates="login_audits")

