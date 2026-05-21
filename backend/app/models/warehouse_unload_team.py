from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class WarehouseUnloadTeam(Base):
    __tablename__ = "EquiposDescargaBodega"
    __table_args__ = (UniqueConstraint("IdBodega", "Nombre", name="UqEquipoDescargaBodegaNombre"),)

    id: Mapped[int] = mapped_column("Id", primary_key=True, autoincrement=True)
    warehouse_id: Mapped[int] = mapped_column(
        "IdBodega", Integer, ForeignKey("Bodegas.Id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column("Nombre", String(80), nullable=False)
    active: Mapped[bool] = mapped_column("Activo", Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column("Orden", Integer, nullable=False, default=0)

    warehouse = relationship("Warehouse", back_populates="unload_teams_rel")
