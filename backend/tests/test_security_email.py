from unittest.mock import patch

from app.services.login_policy import LoginFailureOutcome
from app.services.security_email import dispatch_account_lockout_email


def test_dispatch_account_lockout_email():
    with patch("app.services.security_email.dispatch_notification_email") as dispatch:
        dispatch_account_lockout_email("user@gmail.com", lockout_minutes=15)
    dispatch.assert_called_once()
    assert "bloqueada" in dispatch.call_args[0][1].lower()


def test_login_failure_outcome_blocked():
    outcome = LoginFailureOutcome(consecutive_failures=5, just_blocked=True)
    assert outcome.just_blocked is True
