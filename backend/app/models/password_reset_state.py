from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PasswordResetState(Base):
    __tablename__ = "EstadoResetContrasena"

    credential_id: Mapped[int] = mapped_column(
        "IdCredencial", ForeignKey("Credenciales.IdCredencial", ondelete="CASCADE"), primary_key=True
    )
    must_change_password: Mapped[bool] = mapped_column("DebeCambiarContrasena", Boolean, nullable=False, default=False)
    temporary_issued_at: Mapped[datetime | None] = mapped_column("EmitidoTemporalEn", DateTime(timezone=True), nullable=True)

    credential = relationship("Credential", back_populates="password_reset_state")
