"""Resend sandbox vs SMTP: el proveedor debe recibir correo en el destinatario real cuando hay SMTP."""

from unittest.mock import MagicMock, patch

from app.core.config import settings
from app.services import email_dispatch as dispatch
from app.services.mailer import prefer_smtp_for_real_delivery, public_logo_url


def test_resend_sandbox_inbox_candidates_without_crash(monkeypatch):
    from app.services.email_sandbox import resend_sandbox_inbox_candidates

    monkeypatch.setattr(settings, "resend_sandbox", True)
    monkeypatch.setattr(settings, "resend_api_key", "re_test")
    monkeypatch.setattr(settings, "resend_sandbox_inbox", "inbox@test.com")
    monkeypatch.setattr(settings, "smtp_from_email", "from@test.com")
    candidates = resend_sandbox_inbox_candidates()
    assert candidates[0] == "inbox@test.com"


def test_dispatch_notification_batch_sandbox_no_attribute_error(monkeypatch):
    monkeypatch.setattr(settings, "resend_sandbox", True)
    monkeypatch.setattr(settings, "resend_api_key", "re_test")
    monkeypatch.setattr(settings, "resend_sandbox_inbox", "sandbox@test.com")
    sent: list[tuple[str, str]] = []

    monkeypatch.setattr(
        dispatch,
        "send_appointment_notification_email",
        lambda email, title, body: sent.append((email, title)) or True,
    )
    dispatch.dispatch_notification_emails_batch(
        ["a@b.com", "c@d.com"],
        title="Cita",
        message="Detalle",
    )
    assert len(sent) == 1
    assert sent[0][0] == "sandbox@test.com"


def test_prefer_smtp_in_development_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "smtp_host", "smtp.gmail.com")
    monkeypatch.setattr(settings, "smtp_from_email", "from@test.com")
    monkeypatch.setattr(settings, "smtp_user", "user@test.com")
    monkeypatch.setattr(settings, "smtp_password", "secret")
    monkeypatch.setattr(settings, "resend_sandbox", True)
    monkeypatch.setattr(settings, "resend_api_key", "re_test")
    assert prefer_smtp_for_real_delivery() is True


def test_public_logo_url_uses_stable_https():
    url = public_logo_url()
    assert "ferragro-logo" in url
    assert url.startswith("https://")
    assert "vercel.app" in url or "onrender.com" in url or "githubusercontent" in url


def test_dispatch_provider_sends_provider_before_admins(monkeypatch):
    order: list[str] = []

    def capture(email, title, message):
        order.append(email)

    monkeypatch.setattr(dispatch, "dispatch_notification_email", capture)

    dispatch.dispatch_provider_account_notice(
        provider_email="proveedor@gmail.com",
        provider_name="Vidrios",
        admin_emails=["admin@ferragro.com"],
        action="reactivated",
        detail="Reactivada",
        actor_label="Admin 1",
    )
    assert order[0] == "proveedor@gmail.com"
    assert order[1] == "admin@ferragro.com"
