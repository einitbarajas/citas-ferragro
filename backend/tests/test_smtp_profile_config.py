from app.core.config import Settings


def test_smtp_profile_office365_fills_defaults():
    settings = Settings(
        _env_file=None,
        environment="development",
        database_url="postgresql://u:p@localhost/db",
        secret_key="test-secret-key",
        smtp_profile="office365",
        smtp_from_email="noreply@ferragro.com",
    )
    assert settings.smtp_host == "smtp.office365.com"
    assert settings.smtp_port == 587
    assert settings.smtp_use_tls is True
    assert settings.smtp_use_ssl is False


def test_smtp_profile_does_not_override_explicit_host():
    settings = Settings(
        _env_file=None,
        environment="development",
        database_url="postgresql://u:p@localhost/db",
        secret_key="test-secret-key",
        smtp_profile="gmail",
        smtp_host="smtp.custom.example",
        smtp_from_email="noreply@ferragro.com",
    )
    assert settings.smtp_host == "smtp.custom.example"
