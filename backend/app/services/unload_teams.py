"""Equipos de descarga por bodega (muelles) y sincronización con el contador legacy."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.appointment import Appointment, AppointmentStatus
from app.models.warehouse import Warehouse
from app.models.warehouse_unload_team import WarehouseUnloadTeam

_TERMINAL_APPOINTMENT_STATUSES = (
    AppointmentStatus.cancelado,
    AppointmentStatus.finalizada,
    AppointmentStatus.no_presentada,
)


def _max_teams() -> int:
    return max(1, int(getattr(settings, "max_unload_teams", 20)))


def _assert_teams_can_be_removed(db: Session, teams: list[WarehouseUnloadTeam]) -> None:
    """Impide desactivar muelles con citas que aún no están canceladas, finalizadas o no presentadas."""
    blocking: list[str] = []
    for team in teams:
        rows = db.execute(
            select(Appointment.id, Appointment.status)
            .where(
                Appointment.warehouse_unload_team_id == team.id,
                Appointment.status.not_in(_TERMINAL_APPOINTMENT_STATUSES),
            )
            .order_by(Appointment.start_time.asc())
            .limit(3)
        ).all()
        for appt_id, status in rows:
            blocking.append(f'"{team.name}" (cita #{appt_id}, {status.value})')
    if blocking:
        shown = "; ".join(blocking[:5])
        extra = f" y {len(blocking) - 5} más" if len(blocking) > 5 else ""
        raise HTTPException(
            status_code=409,
            detail=(
                "No se puede reducir el número de muelles: hay citas activas en "
                f"{shown}{extra}. Finaliza, cancela o reprograma esas citas e intenta de nuevo."
            ),
        )


def sync_warehouse_unload_teams(db: Session, warehouse_id: int, target_count: int | None = None) -> list[WarehouseUnloadTeam]:
    """Asegura que la bodega tenga exactamente target_count equipos activos (o usa warehouse.unload_teams)."""
    warehouse = db.get(Warehouse, warehouse_id)
    if not warehouse:
        raise HTTPException(status_code=404, detail="Bodega no encontrada")
    if target_count is None:
        count = max(1, min(int(warehouse.unload_teams or 1), _max_teams()))
    else:
        count = max(1, min(int(target_count), _max_teams()))
        warehouse.unload_teams = count

    existing = list(
        db.execute(
            select(WarehouseUnloadTeam)
            .where(WarehouseUnloadTeam.warehouse_id == warehouse_id)
            .order_by(WarehouseUnloadTeam.sort_order, WarehouseUnloadTeam.id)
        )
        .scalars()
        .all()
    )

    if len(existing) < count:
        for n in range(len(existing) + 1, count + 1):
            db.add(
                WarehouseUnloadTeam(
                    warehouse_id=warehouse_id,
                    name=f"Equipo {n}",
                    active=True,
                    sort_order=n - 1,
                )
            )
        db.flush()
        existing = list(
            db.execute(
                select(WarehouseUnloadTeam)
                .where(WarehouseUnloadTeam.warehouse_id == warehouse_id)
                .order_by(WarehouseUnloadTeam.sort_order, WarehouseUnloadTeam.id)
            )
            .scalars()
            .all()
        )

    if count < len(existing):
        _assert_teams_can_be_removed(db, existing[count:])

    for idx, team in enumerate(existing):
        team.sort_order = idx
        was_active = team.active
        becoming_inactive = idx >= count and was_active
        becoming_active = idx < count and not was_active
        team.active = idx < count
        if becoming_inactive:
            # Libera el nombre para muelles activos (UqEquipoDescargaBodegaNombre es por bodega).
            team.name = f"Equipo {team.id} (inactivo)"
        elif becoming_active and ("(inactivo)" in (team.name or "") or "(reservado)" in (team.name or "")):
            team.name = f"Equipo {idx + 1}"

    db.flush()
    return [t for t in existing if t.active][:count]


def _release_name_conflicts(db: Session, warehouse_id: int, name_by_id: dict[int, str]) -> None:
    """Evita violar UqEquipoDescargaBodegaNombre (incluye filas inactivas antiguas)."""
    for team_id, desired in name_by_id.items():
        conflicts = (
            db.execute(
                select(WarehouseUnloadTeam).where(
                    WarehouseUnloadTeam.warehouse_id == warehouse_id,
                    WarehouseUnloadTeam.name == desired,
                    WarehouseUnloadTeam.id != team_id,
                )
            )
            .scalars()
            .all()
        )
        for other in conflicts:
            suffix = "inactivo" if not other.active else "reservado"
            other.name = f"Equipo {other.id} ({suffix})"


def list_active_unload_teams(db: Session, warehouse_id: int, *, commit: bool = False) -> list[WarehouseUnloadTeam]:
    """Lista equipos activos según Bodegas.EquiposDescarga (sincroniza filas antes)."""
    teams = sync_warehouse_unload_teams(db, warehouse_id)
    if commit:
        db.commit()
    return teams


def get_unload_team_or_raise(db: Session, warehouse_id: int, team_id: int) -> WarehouseUnloadTeam:
    team = db.get(WarehouseUnloadTeam, team_id)
    if not team or team.warehouse_id != warehouse_id or not team.active:
        raise HTTPException(status_code=400, detail="El equipo de descarga no existe o no está activo en esta bodega.")
    return team


def resolve_unload_team_id_for_warehouse(
    db: Session,
    warehouse_id: int,
    team_id: int | None,
    *,
    strict: bool = False,
) -> int | None:
    """Resuelve el muelle de una bodega. En lecturas (strict=False) ignora IDs ajenos o inactivos."""
    teams = list_active_unload_teams(db, warehouse_id)
    if not teams:
        if strict:
            raise HTTPException(
                status_code=400,
                detail="La bodega no tiene equipos de descarga. Configúralos en Bodegas.",
            )
        return None
    if team_id is None:
        return teams[0].id
    team = db.get(WarehouseUnloadTeam, team_id)
    if team and team.warehouse_id == warehouse_id and team.active:
        return team.id
    if strict:
        raise HTTPException(
            status_code=400,
            detail="El equipo de descarga no existe o no está activo en esta bodega.",
        )
    return teams[0].id


def unload_team_to_dict(team: WarehouseUnloadTeam) -> dict:
    return {
        "id": team.id,
        "warehouse_id": team.warehouse_id,
        "name": team.name,
        "active": team.active,
        "sort_order": team.sort_order,
    }


def _active_teams_for_warehouse(db: Session, warehouse_id: int) -> list[WarehouseUnloadTeam]:
    """Equipos activos actuales; sincroniza solo si el conteo no coincide con Bodegas.EquiposDescarga."""
    warehouse = db.get(Warehouse, warehouse_id)
    if not warehouse:
        raise HTTPException(status_code=404, detail="Bodega no encontrada")
    count = max(1, min(int(warehouse.unload_teams or 1), _max_teams()))
    active = list(
        db.execute(
            select(WarehouseUnloadTeam)
            .where(
                WarehouseUnloadTeam.warehouse_id == warehouse_id,
                WarehouseUnloadTeam.active.is_(True),
            )
            .order_by(WarehouseUnloadTeam.sort_order, WarehouseUnloadTeam.id)
        )
        .scalars()
        .all()
    )
    if len(active) != count:
        return sync_warehouse_unload_teams(db, warehouse_id, count)
    return active


def update_warehouse_unload_team_names(
    db: Session,
    warehouse_id: int,
    name_by_id: dict[int, str],
) -> list[WarehouseUnloadTeam]:
    """Actualiza nombres de equipos activos de la bodega (p. ej. Carlos, Rubén)."""
    if not name_by_id:
        raise HTTPException(status_code=400, detail="Indica al menos un equipo con nombre.")

    teams = _active_teams_for_warehouse(db, warehouse_id)
    active_ids = {t.id for t in teams}
    unknown = set(name_by_id) - active_ids
    if unknown:
        raise HTTPException(
            status_code=400,
            detail="Uno o más equipos no pertenecen a esta bodega o no están activos.",
        )

    cleaned: dict[int, str] = {}
    for team_id, raw in name_by_id.items():
        name = (raw or "").strip()
        if len(name) < 1:
            raise HTTPException(status_code=400, detail="El nombre del equipo no puede estar vacío.")
        if len(name) > 80:
            raise HTTPException(status_code=400, detail="El nombre del equipo no puede superar 80 caracteres.")
        cleaned[team_id] = name

    names = list(cleaned.values())
    if len(names) != len(set(names)):
        raise HTTPException(
            status_code=409,
            detail="Los nombres de equipos deben ser distintos entre los muelles activos.",
        )

    _release_name_conflicts(db, warehouse_id, cleaned)
    db.flush()

    for team in teams:
        if team.id in cleaned:
            team.name = cleaned[team.id]

    db.flush()
    return teams
