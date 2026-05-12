import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AppointmentStatus(str, enum.Enum):
    sin_revision = "sin_revision"
    revisado = "revisado"
    finalizada = "finalizada"
    no_presentada = "no_presentada"
    cancelado = "cancelado"


class Appointment(Base):
    __tablename__ = "Citas"

    id: Mapped[int] = mapped_column("Id", primary_key=True, index=True)
    provider_id: Mapped[int] = mapped_column(
        "IdProveedor", Numeric(10, 0), ForeignKey("Proveedores.IdNit"), nullable=False, index=True
    )
    material_description: Mapped[str] = mapped_column("DescripcionMaterial", Text, nullable=False)
    start_time: Mapped[datetime] = mapped_column("FechaHoraInicio", DateTime(timezone=True), nullable=False, index=True)
    duration_minutes: Mapped[int] = mapped_column("DuracionMinutos", Integer, nullable=False, default=90)
    status: Mapped[AppointmentStatus] = mapped_column(
        "Estado", Enum(AppointmentStatus, name="EstadoCita"), nullable=False, default=AppointmentStatus.sin_revision
    )

    provider = relationship("Provider", back_populates="appointments")
    change_logs = relationship("ChangeLog", back_populates="appointment")
    reminder_executions = relationship("ReminderExecution", back_populates="appointment")
