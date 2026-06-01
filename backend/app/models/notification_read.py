from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NotificationRead(Base):
    """Estado de lectura por usuario (documento o NIT proveedor)."""

    __tablename__ = "NotificacionLecturas"
    __table_args__ = (
        UniqueConstraint("IdNotificacion", "IdLector", name="UQ_NotificacionLecturas"),
    )

    id: Mapped[int] = mapped_column("Id", primary_key=True, autoincrement=True)
    notification_id: Mapped[int] = mapped_column(
        "IdNotificacion",
        ForeignKey("Notificaciones.Id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reader_id: Mapped[str] = mapped_column("IdLector", String(30), nullable=False, index=True)
    read_at: Mapped[datetime] = mapped_column("LeidaEn", DateTime(timezone=True), nullable=False)
