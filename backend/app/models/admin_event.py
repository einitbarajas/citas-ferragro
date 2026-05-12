from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AdminEvent(Base):
    __tablename__ = "AuditoriaSistema"

    id: Mapped[int] = mapped_column("Id", primary_key=True, index=True)
    actor_id: Mapped[str] = mapped_column("IdActor", String(30), nullable=False, index=True)
    action: Mapped[str] = mapped_column("Accion", String(80), nullable=False)
    description: Mapped[str] = mapped_column("Descripcion", Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column("CreadoEn", DateTime(timezone=True), nullable=False)
    target_document_id: Mapped[str | None] = mapped_column("DocumentoObjetivo", String(30), nullable=True, index=True)
