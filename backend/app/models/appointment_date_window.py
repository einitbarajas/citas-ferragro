from datetime import date, time

from sqlalchemy import Date, Integer, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AppointmentDateWindow(Base):
    __tablename__ = "FranjasPermitidasCitaFecha"
    __table_args__ = (UniqueConstraint("Fecha", "Orden", name="UqFranjaFechaOrden"),)

    id: Mapped[int] = mapped_column("Id", primary_key=True, autoincrement=True)
    day: Mapped[date] = mapped_column("Fecha", Date, nullable=False, index=True)
    start_local: Mapped[time] = mapped_column("HoraInicio", Time, nullable=False)
    end_local: Mapped[time] = mapped_column("HoraFin", Time, nullable=False)
    sort_order: Mapped[int] = mapped_column("Orden", Integer, nullable=False, default=0)
