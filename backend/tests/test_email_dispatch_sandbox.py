"""Resend sandbox: avisos de citas deben llegar al inbox de prueba."""

from unittest.mock import MagicMock, patch

from app.core.config import settings
from app.services import email_dispatch as dispatch


def test_sandbox_consolidates_recipients(monkeypatch):
    monkeypatch.setattr(settings, "resend_sandbox", True)
    monkeypatch.setattr(settings, "resend_api_key", "re_test")
    monkeypatch.setattr(settings, "resend_sandbox_inbox", "")
    monkeypatch.setattr(settings, "admin_bootstrap_email", "admin@ferragro.com")

    sent: list[tuple[str, str, str]] = []

    def capture(to_email: str, title: str, message: str) -> None:
        sent.append((to_email, title, message))

    monkeypatch.setattr(dispatch, "send_appointment_notification_email", capture)
    dispatch.dispatch_notification_emails_batch(
        ["log@ferragro.com", "proveedor@test.com"],
        title="Cita #1 pendiente",
        message="Horario: 10:00",
    )
    assert len(sent) == 1
    assert sent[0][0] == "admin@ferragro.com"
    assert "log@ferragro.com" in sent[0][2]
    assert "proveedor@test.com" in sent[0][2]
