from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.models.appointment import AppointmentStatus
from app.services.reminder_scheduler import run_reminder_batch


def test_run_reminder_batch_sends_email_for_eligible_appointment():
    now = datetime.now(timezone.utc)
    appt = MagicMock()
    appt.id = 42
    appt.start_time = now + timedelta(hours=24)

    db = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = [appt]
    db.execute.return_value.scalar_one_or_none.return_value = None

    with patch("app.services.reminder_scheduler.SessionLocal") as session_local:
        session_local.return_value.__enter__.return_value = db
        with patch("app.services.reminder_scheduler.notify_appointment_reminder_24h") as notify:
            count = run_reminder_batch()

    assert count == 1
    notify.assert_called_once_with(db, appt)
    db.commit.assert_called_once()
