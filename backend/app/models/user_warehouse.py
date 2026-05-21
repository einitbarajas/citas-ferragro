from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserWarehouse(Base):
    __tablename__ = "UsuariosBodegas"

    document_id: Mapped[str] = mapped_column(
        "IdDocumento",
        ForeignKey("Usuarios.IdDocumento", ondelete="CASCADE"),
        primary_key=True,
    )
    warehouse_id: Mapped[int] = mapped_column(
        "IdBodega",
        ForeignKey("Bodegas.Id", ondelete="CASCADE"),
        primary_key=True,
    )
