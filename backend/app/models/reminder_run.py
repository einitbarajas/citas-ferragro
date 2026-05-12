from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReminderExecution(Base):
    __tablename__ = "EjecucionesRecordatorio"

    id: Mapped[int] = mapped_column("Id", primary_key=True, autoincrement=True)
    appointment_id: Mapped[int] = mapped_column("IdCita", ForeignKey("Citas.Id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column("Tipo", String(40), nullable=False, default="recordatorio_proximo")
    status: Mapped[str] = mapped_column("Estado", String(30), nullable=False)
    detail: Mapped[str | None] = mapped_column("Detalle", Text, nullable=True)
    executed_at: Mapped[datetime] = mapped_column("EjecutadoEn", DateTime(timezone=True), nullable=False)

    appointment = relationship("Appointment", back_populates="reminder_executions", foreign_keys=[appointment_id])

