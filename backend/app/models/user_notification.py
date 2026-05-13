from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserNotification(Base):
    __tablename__ = "Notificaciones"

    id: Mapped[int] = mapped_column("Id", primary_key=True, autoincrement=True)
    recipient_role: Mapped[str] = mapped_column("RolDestinatario", String(20), nullable=False, index=True)
    recipient_provider_id: Mapped[int | None] = mapped_column(
        "IdProveedorDestinatario", Numeric(10, 0), nullable=True, index=True
    )
    appointment_id: Mapped[int] = mapped_column(
        "IdCita", ForeignKey("Citas.Id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column("Tipo", String(40), nullable=False)
    title: Mapped[str] = mapped_column("Titulo", String(160), nullable=False)
    message: Mapped[str] = mapped_column("Mensaje", Text, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column("LeidaEn", DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column("CreadaEn", DateTime(timezone=True), nullable=False)

    appointment = relationship("Appointment", foreign_keys=[appointment_id])
