"""Resend sandbox vs SMTP: el proveedor debe recibir correo en el destinatario real cuando hay SMTP."""

from unittest.mock import MagicMock, patch

from app.core.config import settings
from app.services import email_dispatch as dispatch
from app.services.mailer import prefer_smtp_for_real_delivery, public_logo_url


def test_prefer_smtp_in_development_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "smtp_host", "smtp.gmail.com")
    monkeypatch.setattr(settings, "smtp_from_email", "from@test.com")
    monkeypatch.setattr(settings, "smtp_user", "user@test.com")
    monkeypatch.setattr(settings, "smtp_password", "secret")
    monkeypatch.setattr(settings, "resend_sandbox", True)
    monkeypatch.setattr(settings, "resend_api_key", "re_test")
    assert prefer_smtp_for_real_delivery() is True


def test_public_logo_url_uses_api_assets():
    url = public_logo_url()
    assert "ferragro-logo" in url
    assert "/assets/ferragro-logo.png" in url
    assert url.startswith("https://")


def test_provider_notice_skips_invalid_provider_email(monkeypatch):
    sent: list[str] = []

    def capture(*args, **kwargs):
        sent.append(args[0])

    monkeypatch.setattr(dispatch, "_prepare_smtp_for_send", lambda: True)
    monkeypatch.setattr(dispatch, "send_provider_account_notice_email", lambda email, **kw: sent.append(email) or True)

    dispatch._send_provider_account_blocking(
        "  ",
        provider_name="Test",
        title="Cuenta reactivada",
        detail="Detalle",
        actor_label="Admin",
        is_admin_copy=False,
    )
    assert sent == []


def test_dispatch_provider_sends_provider_before_admins(monkeypatch):
    order: list[str] = []

    def fake_pool(fn, email, **kwargs):
        order.append(f"{email}:{kwargs.get('is_admin_copy')}")

    monkeypatch.setattr(dispatch, "_run_in_email_pool", fake_pool)
    monkeypatch.setattr(dispatch, "_prepare_smtp_for_send", lambda: True)

    dispatch.dispatch_provider_account_notice(
        provider_email="proveedor@gmail.com",
        provider_name="Vidrios",
        admin_emails=["admin@ferragro.com"],
        action="reactivated",
        detail="Reactivada",
        actor_label="Admin 1",
    )
    assert order[0] == "proveedor@gmail.com:False"
    assert order[1] == "admin@ferragro.com:True"
