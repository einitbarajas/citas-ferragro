from datetime import time

from sqlalchemy import Integer, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AppointmentWindow(Base):
    __tablename__ = "FranjasPermitidasCita"

    id: Mapped[int] = mapped_column("Id", primary_key=True, autoincrement=True)
    start_local: Mapped[time] = mapped_column("HoraInicio", Time, nullable=False)
    end_local: Mapped[time] = mapped_column("HoraFin", Time, nullable=False)
    sort_order: Mapped[int] = mapped_column("Orden", Integer, nullable=False, default=0)
