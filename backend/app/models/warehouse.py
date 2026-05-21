from sqlalchemy import Boolean, CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Warehouse(Base):
    __tablename__ = "Bodegas"
    __table_args__ = (
        CheckConstraint(
            '"EquiposDescarga" >= 1 AND "EquiposDescarga" <= 20',
            name="ChkBodegasEquiposDescarga",
        ),
    )

    id: Mapped[int] = mapped_column("Id", primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column("Nombre", String(120), nullable=False, unique=True)
    address: Mapped[str | None] = mapped_column("Direccion", String(255), nullable=True)
    active: Mapped[bool] = mapped_column("Activa", Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column("Orden", Integer, nullable=False, default=0)
    unload_teams: Mapped[int] = mapped_column("EquiposDescarga", Integer, nullable=False, default=1)

    appointments = relationship("Appointment", back_populates="warehouse")
    unload_teams_rel = relationship(
        "WarehouseUnloadTeam",
        back_populates="warehouse",
        order_by="WarehouseUnloadTeam.sort_order, WarehouseUnloadTeam.id",
    )
