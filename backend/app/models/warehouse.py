from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Warehouse(Base):
    __tablename__ = "Bodegas"

    id: Mapped[int] = mapped_column("Id", primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column("Nombre", String(120), nullable=False, unique=True)
    address: Mapped[str | None] = mapped_column("Direccion", String(255), nullable=True)
    active: Mapped[bool] = mapped_column("Activa", Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column("Orden", Integer, nullable=False, default=0)

    appointments = relationship("Appointment", back_populates="warehouse")
