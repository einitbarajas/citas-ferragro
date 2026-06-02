"""Logo en correos: SMTP usa CID; Resend usa URL HTTPS."""

from app.services.email_branding import LOGO_CID, hosted_logo_url, logo_img_html, read_logo_bytes


def test_logo_html_uses_matching_cid_for_smtp():
    html = logo_img_html(use_cid=True)
    assert f"cid:{LOGO_CID}" in html


def test_logo_html_uses_https_url_for_resend():
    html = logo_img_html(use_cid=False)
    assert html.startswith('<img src="https://')
    assert "ferragro-logo" in html
    assert "cid:" not in html


def test_hosted_logo_url_points_to_api_assets():
    url = hosted_logo_url()
    assert url.endswith("/assets/ferragro-logo.png")
    assert url.startswith("https://")


def test_logo_bytes_available_in_repo():
    assert read_logo_bytes() is not None
