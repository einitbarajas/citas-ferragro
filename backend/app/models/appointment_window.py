from datetime import time
from typing import Optional

from sqlalchemy import ForeignKey, Integer, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AppointmentWindow(Base):
    __tablename__ = "FranjasPermitidasCita"

    id: Mapped[int] = mapped_column("Id", primary_key=True, autoincrement=True)
    warehouse_id: Mapped[int] = mapped_column(
        "IdBodega", Integer, ForeignKey("Bodegas.Id"), nullable=False, index=True
    )
    warehouse_unload_team_id: Mapped[Optional[int]] = mapped_column(
        "IdEquipoDescargaBodega",
        Integer,
        ForeignKey("EquiposDescargaBodega.Id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    start_local: Mapped[time] = mapped_column("HoraInicio", Time, nullable=False)
    end_local: Mapped[time] = mapped_column("HoraFin", Time, nullable=False)
    sort_order: Mapped[int] = mapped_column("Orden", Integer, nullable=False, default=0)
