import re

_CORS_VERCEL_FERRAGRO_REGEX = re.compile(
    r"^https://(?:[a-z0-9-]+\.ferragro|[a-z0-9-]+-ferragro)\.vercel\.app$"
)


def _matches(origin: str) -> bool:
    return _CORS_VERCEL_FERRAGRO_REGEX.match(origin) is not None


def test_cors_vercel_ferragro_production_origins():
    assert _matches("https://citas.ferragro.vercel.app")
    assert _matches("https://frontend-ferragro.vercel.app")
    assert _matches("https://frontend-git-main-ferragro.vercel.app")


def test_cors_vercel_ferragro_rejects_unrelated():
    assert not _matches("https://evil.com")
    assert not _matches("http://citas.ferragro.vercel.app")
