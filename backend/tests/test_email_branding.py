"""Logo en correos: CID + adjunto Resend; URL HTTPS como respaldo."""

from app.services.email_branding import (
    DEFAULT_LOGO_URL,
    LOGO_CID,
    hosted_logo_url,
    logo_img_html,
    resend_logo_attachment,
    read_logo_bytes,
)


def test_logo_html_uses_matching_cid_for_smtp():
    html = logo_img_html(use_cid=True)
    assert f"cid:{LOGO_CID}" in html


def test_logo_html_uses_https_url_when_not_cid():
    html = logo_img_html(use_cid=False)
    assert html.startswith('<img src="https://')
    assert "ferragro-logo" in html
    assert "cid:" not in html


def test_hosted_logo_url_uses_vercel_panel_by_default():
    url = hosted_logo_url()
    assert url == DEFAULT_LOGO_URL or url.endswith("/ferragro-logo.png")


def test_resend_attachment_has_matching_content_id():
    att = resend_logo_attachment()
    assert att is not None
    assert att["content_id"] == LOGO_CID
    assert att["filename"] == "ferragro-logo.png"
    assert "content" in att or "path" in att


def test_logo_bytes_available_in_repo():
    assert read_logo_bytes() is not None
