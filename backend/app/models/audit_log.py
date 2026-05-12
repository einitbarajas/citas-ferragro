from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ChangeLog(Base):
    __tablename__ = "HistorialCambios"

    id: Mapped[int] = mapped_column("Id", primary_key=True, index=True)
    actor_id: Mapped[str] = mapped_column("IdActor", String(30), nullable=False, index=True)
    appointment_id: Mapped[int] = mapped_column("IdCita", ForeignKey("Citas.Id"), nullable=False)
    action: Mapped[str] = mapped_column("Accion", String(80), nullable=False)
    description: Mapped[str] = mapped_column("Descripcion", Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column("CreadoEn", DateTime(timezone=True), nullable=False)
    critical_field: Mapped[str | None] = mapped_column("CampoCritico", String(80), nullable=True)
    old_value: Mapped[str | None] = mapped_column("ValorAnterior", Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column("ValorNuevo", Text, nullable=True)

    appointment = relationship("Appointment", back_populates="change_logs")


AuditLog = ChangeLog
