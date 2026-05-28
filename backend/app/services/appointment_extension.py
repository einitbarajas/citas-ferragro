"""Resumen de extensiones de duración por cita (auditoría)."""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.role import Role
from app.models.user import User, UserRole


@dataclass(frozen=True)
class ExtensionSummary:
    logistics_extend_used: bool
    logistics_extend_minutes: int
    total_extend_minutes: int
    original_duration_minutes: int | None


def _parse_minutes(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except ValueError:
        return None


def _logistics_actor_ids(db: Session) -> set[str]:
    rows = (
        db.execute(
            select(User.document_id)
            .join(Role, User.role_id == Role.id)
            .where(Role.name == UserRole.logistica)
        )
        .scalars()
        .all()
    )
    return {str(doc_id) for doc_id in rows}


def _is_logistics_from_description(description: str | None) -> bool:
    text = str(description or "")
    return "[actor_role=Logistica]" in text


def get_extension_summaries(
    db: Session,
    appointment_ids: list[int],
    *,
    current_durations: dict[int, int] | None = None,
) -> dict[int, ExtensionSummary]:
    if not appointment_ids:
        return {}
    logistics_ids = _logistics_actor_ids(db)

    # Incluimos también los "update_field" sobre duración para poder "resetear"
    # el cálculo si la cita se reprograma o su duración vuelve a un valor anterior.
    rows = (
        db.execute(
            select(
                AuditLog.appointment_id,
                AuditLog.actor_id,
                AuditLog.action,
                AuditLog.critical_field,
                AuditLog.old_value,
                AuditLog.new_value,
                AuditLog.description,
            )
            .where(
                AuditLog.appointment_id.in_(appointment_ids),
                AuditLog.action.in_(["extend_duration", "update_field"]),
            )
            .order_by(AuditLog.appointment_id.asc(), AuditLog.id.asc())
        )
        .all()
    )

    by_appt: dict[int, list[tuple[str, str, str | None, str | None, str | None, str | None]]] = {}
    for appt_id, actor_id, action, critical_field, old_val, new_val, description in rows:
        by_appt.setdefault(int(appt_id), []).append(
            (
                str(actor_id),
                str(action),
                str(critical_field) if critical_field is not None else None,
                str(old_val) if old_val is not None else None,
                str(new_val) if new_val is not None else None,
                str(description) if description is not None else None,
            )
        )

    out: dict[int, ExtensionSummary] = {}
    for appt_id in appointment_ids:
        entries = by_appt.get(int(appt_id), [])

        # Segmento base vigente (después del último reset por cambio de duración).
        total_extra = 0
        logistics_extra = 0
        original: int | None = None

        for actor_id, action, critical_field, old_val, new_val, description in entries:
            # Reset: reprogramación/modificación que cambia duration_minutes.
            if action == "update_field" and critical_field in {"duration_minutes", "duracion_minutos"}:
                parsed_new = _parse_minutes(new_val)
                if parsed_new is None:
                    continue
                original = parsed_new
                total_extra = 0
                logistics_extra = 0
                continue

            if action != "extend_duration":
                continue

            old_m = _parse_minutes(old_val)
            new_m = _parse_minutes(new_val)
            if old_m is None or new_m is None or new_m <= old_m:
                continue

            extra = new_m - old_m
            total_extra += extra
            if original is None:
                original = old_m

            role_marked_logistics = _is_logistics_from_description(description)
            if actor_id in logistics_ids or role_marked_logistics:
                logistics_extra += extra

        if original is None and current_durations:
            original = current_durations.get(int(appt_id))

        out[int(appt_id)] = ExtensionSummary(
            logistics_extend_used=logistics_extra > 0,
            logistics_extend_minutes=logistics_extra,
            total_extend_minutes=total_extra,
            original_duration_minutes=original,
        )

    return out
