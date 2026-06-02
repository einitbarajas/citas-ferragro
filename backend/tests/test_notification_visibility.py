"""Visibilidad de notificaciones: actor, serialización, publicación y aislamiento de roles."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.api.notifications import _serialize_notification, _recipient_filter, _scoped_warehouse_clause
from app.models.appointment import AppointmentStatus
from app.models.user import UserRole
from app.models.user_notification import UserNotification
from app.services.appointment_actor import ActorContext, actor_from_principal
from app.services.appointment_notification_events import (
    AppointmentNotificationAction,
    publish_appointment_notification,
)
from app.services.notification_realtime import _should_deliver, _Subscriber


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


def _make_mock_db_for_publish(provider, warehouse):
    """Crea un MagicMock de Session que asigna IDs incrementales en flush."""
    from app.models.provider import Provider
    from app.models.warehouse import Warehouse

    db = MagicMock()
    db.get.side_effect = lambda model, _id: provider if model is Provider else warehouse
    added: list[UserNotification] = []
    _counter = [0]

    def capture_add(row):
        added.append(row)

    def flush_assign_id():
        if added and added[-1].id is None:
            _counter[0] += 1
            added[-1].id = _counter[0]

    db.add.side_effect = capture_add
    db.flush.side_effect = flush_assign_id
    return db, added


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

    db, added = _make_mock_db_for_publish(provider, warehouse)

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


# ---------------------------------------------------------------------------
# Tests de aislamiento: proveedor A no puede ver notificaciones de proveedor B
# ---------------------------------------------------------------------------

def _make_subscriber(role: str, subject: str, warehouse_ids: frozenset[int] = frozenset()) -> _Subscriber:
    import asyncio
    return _Subscriber(
        queue=asyncio.Queue(),
        role=role,
        subject=subject,
        warehouse_ids=warehouse_ids,
    )


def test_sse_provider_only_receives_own_events():
    """Un proveedor solo recibe eventos SSE de sus propias citas (mismo NIT)."""
    sub_a = _make_subscriber(UserRole.proveedor, "900111111")
    sub_b = _make_subscriber(UserRole.proveedor, "900222222")

    # Evento para proveedor 900111111
    assert _should_deliver(sub_a, warehouse_id=1, provider_id=900111111) is True
    assert _should_deliver(sub_b, warehouse_id=1, provider_id=900111111) is False


def test_sse_provider_does_not_receive_other_warehouse():
    """Un proveedor no recibe eventos de otra bodega (solo filtro por NIT)."""
    sub = _make_subscriber(UserRole.proveedor, "900111111")
    # Evento de proveedor diferente en cualquier bodega
    assert _should_deliver(sub, warehouse_id=5, provider_id=900999999) is False


def test_sse_admin_receives_all_events():
    """El administrador recibe eventos de cualquier bodega y cualquier proveedor."""
    sub = _make_subscriber(UserRole.admin, "admin-doc")
    assert _should_deliver(sub, warehouse_id=1, provider_id=900111111) is True
    assert _should_deliver(sub, warehouse_id=99, provider_id=900999999) is True


def test_sse_admin_bodega_receives_only_assigned_warehouses():
    """AdminBodega solo recibe eventos SSE de las bodegas que tiene asignadas."""
    sub = _make_subscriber(UserRole.admin_bodega, "admin-bodega-doc", frozenset({1, 3}))
    assert _should_deliver(sub, warehouse_id=1, provider_id=0) is True
    assert _should_deliver(sub, warehouse_id=3, provider_id=0) is True
    assert _should_deliver(sub, warehouse_id=2, provider_id=0) is False
    assert _should_deliver(sub, warehouse_id=99, provider_id=0) is False


def test_sse_logistica_receives_only_assigned_warehouses():
    """Logística solo recibe eventos SSE de sus bodegas asignadas."""
    sub = _make_subscriber(UserRole.logistica, "logistica-doc", frozenset({2}))
    assert _should_deliver(sub, warehouse_id=2, provider_id=0) is True
    assert _should_deliver(sub, warehouse_id=1, provider_id=0) is False


# ---------------------------------------------------------------------------
# Tests de filtro de notificaciones in-app por recipient_role y recipient_provider_id
# ---------------------------------------------------------------------------

def _make_notification(
    *,
    recipient_role: str,
    recipient_provider_id: int | None = None,
    warehouse_id: int = 1,
    appointment_id: int | None = 10,
) -> UserNotification:
    return UserNotification(
        id=1,
        recipient_role=recipient_role,
        recipient_provider_id=recipient_provider_id,
        appointment_id=appointment_id,
        warehouse_id=warehouse_id,
        provider_id=900111111,
        kind="cita_creada",
        title="Cita creada",
        message="Mensaje",
        actor_id="sistema",
        actor_role="Sistema",
        actor_label="el sistema",
        action="cita_creada",
        appointment_status="sin_revision",
        created_at=datetime.now(timezone.utc),
    )


def test_provider_notification_has_isolated_provider_id():
    """La notificación del proveedor lleva recipient_provider_id correcto."""
    notif = _make_notification(
        recipient_role=UserRole.proveedor,
        recipient_provider_id=900111111,
    )
    assert notif.recipient_role == UserRole.proveedor
    assert int(notif.recipient_provider_id) == 900111111


def test_staff_notification_has_no_provider_id():
    """Las notificaciones de staff no llevan recipient_provider_id."""
    for role in (UserRole.admin, UserRole.admin_bodega, UserRole.logistica):
        notif = _make_notification(recipient_role=role, recipient_provider_id=None)
        assert notif.recipient_provider_id is None


def test_publish_provider_notification_recipient_provider_id_matches(monkeypatch):
    """El recipient_provider_id de la notificación de proveedor debe coincidir con provider_id de la cita."""
    appointment = MagicMock()
    appointment.id = 55
    appointment.warehouse_id = 7
    appointment.provider_id = 900777777
    appointment.status = AppointmentStatus.sin_revision
    appointment.duration_minutes = 60
    appointment.start_time = MagicMock()

    provider = MagicMock(company_name="Empresa XYZ")
    warehouse = MagicMock(name="Bodega XYZ")

    db, added = _make_mock_db_for_publish(provider, warehouse)

    monkeypatch.setattr("app.services.appointment_notification_events._dispatch_notification_emails", lambda *a, **k: None)
    monkeypatch.setattr("app.services.appointment_notification_events._emit_realtime", lambda **k: None)
    monkeypatch.setattr(
        "app.services.appointment_notification_events._appointment_email_context",
        lambda _db, _appt: MagicMock(
            provider_name="Empresa XYZ",
            warehouse_name="Bodega XYZ",
            start_label="01/06/2026 10:00",
            duration_minutes=60,
        ),
    )

    actor = ActorContext(actor_id="900777777", actor_role=UserRole.proveedor, actor_label="el proveedor con NIT 900777777")
    publish_appointment_notification(db, appointment, action=AppointmentNotificationAction.created, actor=actor, send_email=False)

    provider_rows = [r for r in added if r.recipient_role == UserRole.proveedor]
    assert len(provider_rows) == 1
    assert int(provider_rows[0].recipient_provider_id) == 900777777

    # El proveedor 900888888 NO debe tener ninguna notificación dirigida a él
    other_provider_rows = [r for r in added if r.recipient_provider_id == 900888888]
    assert len(other_provider_rows) == 0


def test_publish_does_not_create_cross_provider_notifications(monkeypatch):
    """Cuando se crea una cita para proveedor A, proveedor B no recibe notificaciones."""
    appointment = MagicMock()
    appointment.id = 77
    appointment.warehouse_id = 1
    appointment.provider_id = 900111111
    appointment.status = AppointmentStatus.sin_revision
    appointment.duration_minutes = 90
    appointment.start_time = MagicMock()

    provider = MagicMock(company_name="Proveedor A")
    warehouse = MagicMock(name="Bodega Central")

    db, added = _make_mock_db_for_publish(provider, warehouse)

    monkeypatch.setattr("app.services.appointment_notification_events._dispatch_notification_emails", lambda *a, **k: None)
    monkeypatch.setattr("app.services.appointment_notification_events._emit_realtime", lambda **k: None)
    monkeypatch.setattr(
        "app.services.appointment_notification_events._appointment_email_context",
        lambda _db, _appt: MagicMock(
            provider_name="Proveedor A",
            warehouse_name="Bodega Central",
            start_label="01/06/2026 10:00",
            duration_minutes=90,
        ),
    )

    actor = ActorContext(actor_id="1001", actor_role=UserRole.admin, actor_label="el Administrador")
    publish_appointment_notification(db, appointment, action=AppointmentNotificationAction.created, actor=actor, send_email=False)

    # Solo proveedor 900111111 debe tener notificación de proveedor
    provider_rows = [r for r in added if r.recipient_role == UserRole.proveedor]
    assert all(int(r.recipient_provider_id) == 900111111 for r in provider_rows), (
        "No deben existir notificaciones de proveedor con NIT diferente a 900111111"
    )

    # Proveedor B (900222222) no tiene ninguna notificación
    b_rows = [r for r in added if r.recipient_provider_id == 900222222]
    assert len(b_rows) == 0


# ---------------------------------------------------------------------------
# Tests de auditoría: actor_role se guarda en ChangeLog
# ---------------------------------------------------------------------------

def test_record_audit_stores_actor_role(monkeypatch):
    """record_audit debe guardar actor_role en el log de cambios."""
    from app.services.appointment_notification_events import record_audit
    from app.models.audit_log import AuditLog

    db = MagicMock()
    added_log: list[AuditLog] = []
    db.add.side_effect = added_log.append

    actor = ActorContext(
        actor_id="1001",
        actor_role=UserRole.admin_bodega,
        actor_label="el Administrador de Bodega Carlos",
        ip_address="192.168.1.1",
    )
    record_audit(db, appointment_id=42, actor=actor, action="update_field", description="Campo actualizado")

    assert len(added_log) == 1
    log = added_log[0]
    assert log.actor_role == UserRole.admin_bodega
    assert log.actor_id == "1001"
    assert log.ip_address == "192.168.1.1"


def test_record_audit_stores_provider_actor_role(monkeypatch):
    """Cuando el actor es proveedor, actor_role debe quedar como 'Proveedor'."""
    from app.services.appointment_notification_events import record_audit
    from app.models.audit_log import AuditLog

    db = MagicMock()
    added_log: list[AuditLog] = []
    db.add.side_effect = added_log.append

    actor = ActorContext(
        actor_id="900123456",
        actor_role=UserRole.proveedor,
        actor_label="el proveedor con NIT 900123456",
        ip_address=None,
    )
    record_audit(db, appointment_id=10, actor=actor, action="provider_cancel", description="Proveedor cancela")

    assert len(added_log) == 1
    assert added_log[0].actor_role == UserRole.proveedor
