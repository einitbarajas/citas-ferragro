from datetime import date, time

from typing import Optional

from sqlalchemy import Date, ForeignKey, Index, Integer, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AppointmentDateWindow(Base):
    __tablename__ = "FranjasPermitidasCitaFecha"
    __table_args__ = (
        Index(
            "UqFranjaFechaBodegaOrdenCompartido",
            "Fecha",
            "IdBodega",
            "Orden",
            unique=True,
            postgresql_where="IdEquipoDescargaBodega IS NULL",
        ),
        Index(
            "UqFranjaFechaBodegaEquipoOrden",
            "Fecha",
            "IdBodega",
            "IdEquipoDescargaBodega",
            "Orden",
            unique=True,
            postgresql_where="IdEquipoDescargaBodega IS NOT NULL",
        ),
    )

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
    day: Mapped[date] = mapped_column("Fecha", Date, nullable=False, index=True)
    start_local: Mapped[time] = mapped_column("HoraInicio", Time, nullable=False)
    end_local: Mapped[time] = mapped_column("HoraFin", Time, nullable=False)
    sort_order: Mapped[int] = mapped_column("Orden", Integer, nullable=False, default=0)
