"""Visibilidad de notificaciones: actor, serialización y publicación."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.api.notifications import _serialize_notification
from app.models.appointment import AppointmentStatus
from app.models.user import UserRole
from app.models.user_notification import UserNotification
from app.services.appointment_actor import ActorContext, actor_from_principal
from app.services.appointment_notification_events import (
    AppointmentNotificationAction,
    publish_appointment_notification,
)


class _FakeUser:
    document_id = "1001"
    full_name = "Juan Pérez"


class _FakePrincipal:
    def __init__(self, role_name: str, subject: str, user=None):
        self.subject = subject
        self.role_name = role_name
        self.user = user
        self.document_id = subject
        self.provider = None


def test_provider_actor_label_uses_nit():
    principal = _FakePrincipal(UserRole.proveedor, "900123456")
    actor = actor_from_principal(principal)  # type: ignore[arg-type]
    assert "900123456" in actor.actor_label
    assert "NIT" in actor.actor_label


def test_staff_actor_label_includes_name():
    principal = _FakePrincipal(UserRole.admin, "1001", user=_FakeUser())
    actor = actor_from_principal(principal)  # type: ignore[arg-type]
    assert "Juan Pérez" in actor.actor_label
    assert "Administrador" in actor.actor_label


def test_serialize_includes_actor_fields():
    row = UserNotification(
        recipient_role=UserRole.admin,
        appointment_id=1,
        warehouse_id=2,
        provider_id=9001,
        kind="cita_actualizada",
        title="T",
        message="M",
        actor_id="1",
        actor_role=UserRole.admin,
        actor_label="el Administrador X",
        action="cita_actualizada",
        appointment_status=AppointmentStatus.sin_revision.value,
        created_at=datetime.now(timezone.utc),
    )
    data = _serialize_notification(row, read_at=None)
    assert data["actor_label"] == "el Administrador X"
    assert data["action"] == "cita_actualizada"
    assert data["warehouse_id"] == 2
    assert data["read"] is False


def test_publish_persists_four_recipient_roles(monkeypatch):
    appointment = MagicMock()
    appointment.id = 12
    appointment.warehouse_id = 3
    appointment.provider_id = 9001234567
    appointment.status = AppointmentStatus.sin_revision
    appointment.duration_minutes = 90
    appointment.start_time = MagicMock()

    provider = MagicMock(company_name="Proveedor Test")
    warehouse = MagicMock(name="Bodega Central")

    db = MagicMock()
    from app.models.provider import Provider
    from app.models.warehouse import Warehouse

    db.get.side_effect = lambda model, _id: provider if model is Provider else warehouse
    added: list[UserNotification] = []

    def capture_add(row):
        added.append(row)

    db.add.side_effect = capture_add
    db.flush.side_effect = lambda: None

    monkeypatch.setattr(
        "app.services.appointment_notification_events._dispatch_notification_emails",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "app.services.appointment_notification_events._emit_realtime",
        lambda **k: None,
    )
    monkeypatch.setattr(
        "app.services.appointment_notification_events._appointment_email_context",
        lambda _db, _appt: MagicMock(
            provider_name="Proveedor Test",
            warehouse_name="Bodega Central",
            start_label="01/06/2026 10:00",
            duration_minutes=90,
        ),
    )

    actor = ActorContext(
        actor_id="9001234567",
        actor_role=UserRole.proveedor,
        actor_label="el proveedor con NIT 9001234567",
    )
    publish_appointment_notification(
        db,
        appointment,
        action=AppointmentNotificationAction.updated,
        actor=actor,
        send_email=False,
    )
    roles = {r.recipient_role for r in added}
    assert roles == {
        UserRole.admin,
        UserRole.logistica,
        UserRole.admin_bodega,
        UserRole.proveedor,
    }
    provider_row = next(r for r in added if r.recipient_role == UserRole.proveedor)
    assert int(provider_row.recipient_provider_id or 0) == 9001234567
    assert "NIT 9001234567" in provider_row.message
