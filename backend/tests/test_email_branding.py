"""Logo único transparente en correos."""

from app.services.email_branding import (
    LOGO_CID,
    LOGO_FILENAME,
    hosted_logo_url,
    logo_img_html,
    read_logo_bytes,
    resend_logo_attachment,
)


def test_single_logo_html_with_cid():
    html = logo_img_html(use_cid=True)
    assert html.count("<img") == 1
    assert f"cid:{LOGO_CID}" in html
    assert "ferragro-logo-light" not in html
    assert "ferragro-logo-dark" not in html


def test_single_logo_html_https():
    html = logo_img_html(use_cid=False)
    assert html.count("<img") == 1
    assert "ferragro-logo-email" in html
    assert "cid:" not in html


def test_hosted_logo_url():
    assert "ferragro-logo-email.png" in hosted_logo_url()


def test_resend_attachment():
    att = resend_logo_attachment()
    assert att is not None
    assert att["content_id"] == LOGO_CID
    assert att["filename"] == LOGO_FILENAME


def test_logo_bytes_in_repo():
    assert read_logo_bytes() is not None
