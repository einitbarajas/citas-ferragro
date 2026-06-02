"""Logo en correos: dual light/dark + adjuntos Resend."""

from app.services.email_branding import (
    LOGO_CID_DARK,
    LOGO_CID_LIGHT,
    hosted_logo_url,
    logo_img_html,
    read_logo_bytes_dark,
    read_logo_bytes_light,
    resend_logo_attachments,
)


def test_logo_html_includes_light_and_dark_cids():
    html = logo_img_html(use_cid=True)
    assert f"cid:{LOGO_CID_LIGHT}" in html
    assert f"cid:{LOGO_CID_DARK}" in html
    assert "prefers-color-scheme" in html


def test_logo_html_https_urls_when_not_cid():
    html = logo_img_html(use_cid=False)
    assert "ferragro-logo-email-light" in html
    assert "ferragro-logo-email-dark" in html
    assert "cid:" not in html


def test_hosted_logo_urls():
    assert "ferragro-logo-email-light" in hosted_logo_url(dark=False)
    assert "ferragro-logo-email-dark" in hosted_logo_url(dark=True)


def test_resend_attachments_have_both_content_ids():
    attachments = resend_logo_attachments()
    assert len(attachments) >= 2
    ids = {a["content_id"] for a in attachments}
    assert LOGO_CID_LIGHT in ids
    assert LOGO_CID_DARK in ids


def test_logo_bytes_available_in_repo():
    assert read_logo_bytes_light() is not None
    assert read_logo_bytes_dark() is not None
