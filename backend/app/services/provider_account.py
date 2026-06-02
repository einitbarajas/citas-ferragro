"""Suspensión, purga y notificaciones de cuentas proveedor (solo proveedores; no aplica a staff)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.admin_event import AdminEvent
from app.models.appointment import Appointment
from app.models.audit_log import ChangeLog
from app.models.login_audit import LoginAudit
from app.models.provider import Provider, ProviderAccountStatus
from app.models.user_notification import UserNotification
from app.services.auth_sessions import revoke_all_refresh_for_credential
from app.services.credential_cleanup import delete_credential_fully
from app.services.email_dispatch import dispatch_provider_account_notice
from app.services.email_utils import dedupe_emails
from app.services.notification_service import admin_notification_emails

logger = logging.getLogger(__name__)


def provider_purge_after_days() -> int:
    return max(1, int(getattr(settings, "provider_purge_after_days", 180)))


def _appointments_count(db: Session, nit: int) -> int:
    return int(
        db.execute(select(func.count()).select_from(Appointment).where(Appointment.provider_id == nit)).scalar_one()
        or 0
    )


def _last_login_at(db: Session, credential_id: int) -> datetime | None:
    return db.execute(
        select(func.max(LoginAudit.created_at)).where(
            LoginAudit.credential_id == credential_id,
            LoginAudit.success.is_(True),
        )
    ).scalar_one_or_none()


def build_provider_out_dict(db: Session, provider: Provider) -> dict:
    from app.schemas.crud import ProviderOut

    base = ProviderOut.model_validate(provider).model_dump()
    base["status"] = provider.status or ProviderAccountStatus.activo
    base["suspended_at"] = provider.suspended_at
    base["suspension_reason"] = provider.suspension_reason
    base["purge_scheduled_at"] = provider.purge_scheduled_at
    base["appointments_count"] = _appointments_count(db, int(provider.nit))
    base["last_login_at"] = _last_login_at(db, provider.credential_id) if provider.credential_id else None
    return base


def notify_provider_and_admins(
    db: Session,
    *,
    provider: Provider,
    action: str,
    detail: str,
    actor_label: str,
    actor_email: str | None = None,
) -> None:
    if provider.credential and provider.credential.email:
        email = str(provider.credential.email).strip()
    else:
        email = str(provider.company_email or "").strip()
    if not email:
        logger.warning(
            "Proveedor NIT %s sin correo de sesión; aviso solo a administradores (action=%s)",
            provider.nit,
            action,
        )
    admin_emails = admin_notification_emails(db)
    if actor_email:
        admin_emails = dedupe_emails([*admin_emails, actor_email])
    dispatch_provider_account_notice(
        provider_email=str(email),
        provider_name=provider.company_name,
        admin_emails=admin_emails,
        action=action,
        detail=detail,
        actor_label=actor_label,
    )


def _delete_provider_appointments_and_history(db: Session, nit: int) -> int:
    appt_ids = list(
        db.execute(select(Appointment.id).where(Appointment.provider_id == nit)).scalars().all()
    )
    if not appt_ids:
        return 0
    db.execute(delete(ChangeLog).where(ChangeLog.appointment_id.in_(appt_ids)))
    db.execute(delete(UserNotification).where(UserNotification.appointment_id.in_(appt_ids)))
    db.execute(delete(Appointment).where(Appointment.provider_id == nit))
    return len(appt_ids)


def purge_provider_account(
    db: Session,
    provider: Provider,
    *,
    actor_id: str | None,
    log_description: str,
    log_action: str = "provider_purge",
    notify: bool = True,
) -> None:
    nit = int(provider.nit)
    company = provider.company_name
    email = provider.company_email
    cid = provider.credential_id
    removed_appts = _delete_provider_appointments_and_history(db, nit)

    db.add(
        AdminEvent(
            actor_id=actor_id or "sistema",
            action=log_action,
            description=log_description,
            created_at=datetime.now(timezone.utc),
            target_document_id=str(nit),
        )
    )

    if notify:
        notify_provider_and_admins(
            db,
            provider=provider,
            action="purged",
            detail=(
                f"Se eliminó la cuenta y datos operativos del proveedor {company} (NIT {nit}). "
                f"Citas eliminadas: {removed_appts}. Se conserva el registro en auditoría del sistema."
            ),
            actor_label=actor_id or "Sistema",
        )

    revoke_all_refresh_for_credential(db, cid)
    db.delete(provider)
    db.flush()
    delete_credential_fully(db, cid)


def suspend_provider(
    db: Session,
    provider: Provider,
    *,
    reason: str,
    actor_id: str,
    actor_email: str | None = None,
) -> Provider:
    if provider.status == ProviderAccountStatus.suspendido:
        raise HTTPException(status_code=400, detail="El proveedor ya está suspendido")
    now = datetime.now(timezone.utc)
    provider.status = ProviderAccountStatus.suspendido
    provider.suspended_at = now
    provider.suspension_reason = reason.strip()
    provider.suspended_by = actor_id
    provider.purge_scheduled_at = now + timedelta(days=provider_purge_after_days())
    revoke_all_refresh_for_credential(db, provider.credential_id)
    notify_provider_and_admins(
        db,
        provider=provider,
        action="suspended",
        detail=(
            f"Tu cuenta fue suspendida. Motivo: {provider.suspension_reason}. "
            f"Los datos se eliminarán automáticamente el "
            f"{provider.purge_scheduled_at.astimezone(timezone.utc).strftime('%d/%m/%Y')} "
            f"salvo registros de auditoría."
        ),
        actor_label=f"Admin {actor_id}",
        actor_email=actor_email,
    )
    return provider


def reactivate_provider(db: Session, provider: Provider, *, actor_id: str) -> Provider:
    if provider.status != ProviderAccountStatus.suspendido:
        raise HTTPException(status_code=400, detail="El proveedor no está suspendido")
    provider.status = ProviderAccountStatus.activo
    provider.suspended_at = None
    provider.suspension_reason = None
    provider.suspended_by = None
    provider.purge_scheduled_at = None
    notify_provider_and_admins(
        db,
        provider=provider,
        action="reactivated",
        detail="Tu cuenta de proveedor fue reactivada. Ya puedes iniciar sesión y agendar citas.",
        actor_label=f"Admin {actor_id}",
    )
    return provider


def delete_provider_immediate(
    db: Session,
    provider: Provider,
    *,
    actor_id: str,
    force_with_appointments: bool = False,
) -> None:
    nit = int(provider.nit)
    appt_count = _appointments_count(db, nit)
    if appt_count > 0 and not force_with_appointments:
        raise HTTPException(
            status_code=400,
            detail=(
                f"El proveedor tiene {appt_count} cita(s). Suspende la cuenta en lugar de eliminarla; "
                "tras 6 meses suspendido se purgarán datos automáticamente (se conserva auditoría)."
            ),
        )
    name_snapshot = provider.company_name
    notify_provider_and_admins(
        db,
        provider=provider,
        action="deleted",
        detail=(
            f"La cuenta del proveedor {name_snapshot} (NIT {nit}) fue eliminada por el administrador. "
            f"Citas asociadas eliminadas: {appt_count}."
        ),
        actor_label=f"Admin {actor_id}",
    )
    purge_provider_account(
        db,
        provider,
        actor_id=actor_id,
        log_description=f"Eliminó proveedor {name_snapshot} (NIT {nit}); citas: {appt_count}",
        log_action="provider_delete",
        notify=False,
    )


def providers_due_for_purge(db: Session) -> list[Provider]:
    now = datetime.now(timezone.utc)
    return list(
        db.execute(
            select(Provider).where(
                Provider.status == ProviderAccountStatus.suspendido,
                Provider.purge_scheduled_at.is_not(None),
                Provider.purge_scheduled_at <= now,
            )
        )
        .scalars()
        .all()
    )


def format_provider_update_detail(before: dict, after: dict) -> str:
    labels = {
        "company_name": "Empresa",
        "company_email": "Correo",
        "contact_name": "Responsable",
        "contact_document": "Documento responsable",
        "verification_digit": "Dígito verificación",
        "unload_teams": "Equipos de descarga",
    }
    parts: list[str] = []
    for key, label in labels.items():
        old = before.get(key)
        new = after.get(key)
        if old != new and new is not None:
            parts.append(f"{label}: {old} → {new}")
    if before.get("password_changed"):
        parts.append("Contraseña: actualizada por administrador")
    return "; ".join(parts) if parts else "Datos de cuenta actualizados."
