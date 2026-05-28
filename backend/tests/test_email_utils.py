from app.services.email_utils import dedupe_emails, is_deliverable_email, normalize_email


def test_normalize_email_strips_and_extracts_angle_brackets():
    assert normalize_email("  user@gmail.com  ") == "user@gmail.com"
    assert normalize_email("Alejandra <alej@outlook.com>") == "alej@outlook.com"


def test_is_deliverable_accepts_common_providers():
    assert is_deliverable_email("user@gmail.com")
    assert is_deliverable_email("user@ferragro.com")
    assert is_deliverable_email("user@hotmail.com")
    assert not is_deliverable_email("invalid")
    assert not is_deliverable_email("")


def test_dedupe_emails_ignores_invalid_and_duplicates():
    result = dedupe_emails(
        [
            "a@gmail.com",
            "A@gmail.com",
            "b@outlook.com",
            "  ",
            "malformed",
            "b@outlook.com",
        ]
    )
    assert result == ["a@gmail.com", "b@outlook.com"]
