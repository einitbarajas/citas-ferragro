from unittest.mock import MagicMock, patch

from app.services.email_delivery import deliver_with_retry, prepare_mail_transport


def test_deliver_with_retry_succeeds_on_second_attempt():
    calls = {"n": 0}

    def send_once():
        calls["n"] += 1
        return calls["n"] >= 2

    with patch("app.services.email_delivery.prepare_mail_transport", return_value=True):
        with patch("app.services.email_delivery.active_email_provider_label", return_value="resend"):
            result = deliver_with_retry(
                send_once,
                recipient="user@gmail.com",
                subject="Test",
                kind="notification",
                max_attempts=3,
            )

    assert result.ok is True
    assert result.attempts == 2
    assert calls["n"] == 2


def test_deliver_with_retry_fails_when_transport_never_ready():
    with patch("app.services.email_delivery.prepare_mail_transport", return_value=False):
        with patch("app.services.email_delivery.active_email_provider_label", return_value="none"):
            with patch("app.services.email_delivery.time.sleep"):
                result = deliver_with_retry(
                    lambda: True,
                    recipient="user@outlook.com",
                    subject="Test",
                    kind="notification",
                    max_attempts=2,
                )

    assert result.ok is False
    assert result.error == "mail_transport_not_ready"


def test_prepare_mail_transport_uses_resend_when_ready():
    with patch("app.core.smtp_env_loader.overlay_render_smtp_secret"):
        with patch("app.core.config.refresh_smtp_settings"):
            with patch("app.services.email_delivery.settings") as mock_settings:
                mock_settings.is_production = True
                mock_settings.brevo_send_ready = False
                mock_settings.resend_send_ready = True
                assert prepare_mail_transport() is True
