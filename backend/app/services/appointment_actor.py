"""Etiquetas de actor para notificaciones y auditoría."""
from __future__ import annotations

from dataclasses import dataclass

from app.api.deps import SecurityPrincipal
from app.models.user import UserRole


@dataclass(frozen=True)
class ActorContext:
    actor_id: str
    actor_role: str
    actor_label: str
    ip_address: str | None = None


_ROLE_LABELS = {
    UserRole.admin: "Administrador",
    UserRole.admin_bodega: "Administrador de Bodega",
    UserRole.logistica: "Usuario de Logística",
    UserRole.proveedor: "Proveedor",
}


def actor_from_principal(principal: SecurityPrincipal, *, ip_address: str | None = None) -> ActorContext:
    role = principal.role_name
    if role == UserRole.proveedor:
        nit = str(principal.subject).strip()
        return ActorContext(
            actor_id=nit,
            actor_role=role,
            actor_label=f"el proveedor con NIT {nit}",
            ip_address=ip_address,
        )
    name = ""
    if principal.user and principal.user.full_name:
        name = principal.user.full_name.strip()
    role_label = _ROLE_LABELS.get(role, role)
    if name:
        display = f"el {role_label} {name}"
    else:
        display = f"el {role_label} (documento {principal.document_id})"
    return ActorContext(
        actor_id=str(principal.document_id),
        actor_role=role,
        actor_label=display,
        ip_address=ip_address,
    )


def system_actor(*, action: str = "sistema") -> ActorContext:
    return ActorContext(
        actor_id="sistema",
        actor_role="Sistema",
        actor_label="el sistema",
        ip_address=None,
    )
