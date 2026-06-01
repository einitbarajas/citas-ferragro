#!/usr/bin/env python3
"""Sube RESEND + SMTP a Render usando .env / smtp-render.env (sin imprimir secretos)."""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SERVICE_ID = "srv-d82dvanaqgkc739362u0"
HEALTH_URL = "https://ferragro-api.onrender.com/health"
RENDER_API = "https://api.render.com/v1"


def load_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", line)
        if not m:
            continue
        out[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return out


def merge_env(repo: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for name in (".env", "smtp-render.env"):
        env.update(load_dotenv(repo / name))
    for key in ("RENDER_API_KEY", "RESEND_API_KEY", "RENDER_DEPLOY_HOOK"):
        if os.environ.get(key):
            env[key] = os.environ[key]
    cli = Path.home() / ".render" / "cli.yaml"
    if not env.get("RENDER_API_KEY") and cli.is_file():
        raw = cli.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"(?m)^\s*key:\s*(rnd_\S+)\s*$", raw)
        if m:
            env["RENDER_API_KEY"] = m.group(1).strip()
            exp = re.search(r"(?m)^\s*expires_at:\s*(\d+)\s*$", raw)
            if exp and int(exp.group(1)) < time.time():
                print("Aviso: token Render CLI puede estar expirado; si falla, usa API key nueva.")
    return env


def render_put(token: str, path: str, body: dict) -> None:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{RENDER_API}{path}",
        data=data,
        method="PUT",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        if resp.status >= 300:
            raise RuntimeError(f"HTTP {resp.status}")


def render_post(token: str, path: str, body: dict | None = None) -> None:
    data = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(
        f"{RENDER_API}{path}",
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        if resp.status >= 300:
            raise RuntimeError(f"HTTP {resp.status}")


def set_env(token: str, key: str, value: str) -> None:
    render_put(token, f"/services/{SERVICE_ID}/env-vars/{key}", {"key": key, "value": value})
    print(f"  OK {key}")


def wait_health(max_attempts: int = 30) -> bool:
    for i in range(1, max_attempts + 1):
        time.sleep(20)
        try:
            req = urllib.request.Request(HEALTH_URL, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read().decode())
            d = data.get("data") or {}
            enabled = d.get("email_enabled")
            resend = d.get("resend_ready")
            provider = d.get("email_provider")
            build = d.get("build_id")
            print(f"  [{i}] email_enabled={enabled} resend_ready={resend} provider={provider} build={build}")
            if enabled and resend:
                return True
        except Exception as exc:
            print(f"  [{i}] esperando... ({exc})")
    return False


def main() -> int:
    import sys

    repo = Path(__file__).resolve().parents[1]
    env = merge_env(repo)
    if len(sys.argv) > 1 and sys.argv[1].startswith("rnd_"):
        env["RENDER_API_KEY"] = sys.argv[1].strip()

    render_key = env.get("RENDER_API_KEY", "").strip()
    resend_key = env.get("RESEND_API_KEY", "").strip()
    if not resend_key:
        print("ERROR: falta RESEND_API_KEY en .env o smtp-render.env")
        return 1
    if not render_key:
        print("ERROR: falta RENDER_API_KEY (https://dashboard.render.com/u/settings#api-keys)")
        print("  Añade en .env: RENDER_API_KEY=rnd_...")
        print("  O pega smtp-render.env en Render Environment y haz Manual Deploy.")
        return 1

    smtp_vars = {
        "SMTP_PROFILE": env.get("SMTP_PROFILE", "gmail"),
        "SMTP_HOST": env.get("SMTP_HOST", ""),
        "SMTP_PORT": env.get("SMTP_PORT", "587"),
        "SMTP_USER": env.get("SMTP_USER", ""),
        "SMTP_PASSWORD": re.sub(r"\s", "", env.get("SMTP_PASSWORD", "")),
        "SMTP_FROM_EMAIL": env.get("SMTP_FROM_EMAIL", env.get("SMTP_USER", "")),
        "SMTP_FROM_NAME": env.get("SMTP_FROM_NAME", "Ferragro"),
        "SMTP_USE_TLS": env.get("SMTP_USE_TLS", "true"),
        "SMTP_USE_SSL": env.get("SMTP_USE_SSL", "false"),
        "RESEND_API_KEY": resend_key,
        "RESEND_SANDBOX": env.get("RESEND_SANDBOX", "true"),
    }
    if env.get("RESEND_FROM_EMAIL"):
        smtp_vars["RESEND_FROM_EMAIL"] = env["RESEND_FROM_EMAIL"]
    if env.get("BREVO_API_KEY"):
        smtp_vars["BREVO_API_KEY"] = env["BREVO_API_KEY"]

    print("Subiendo variables a Render...")
    try:
        for key, value in smtp_vars.items():
            if not value and key not in ("RESEND_SANDBOX", "SMTP_USE_SSL", "SMTP_USE_TLS"):
                continue
            set_env(render_key, key, value)
        secret_body = "\n".join(f"{k}={v}" for k, v in smtp_vars.items())
        try:
            render_put(
                render_key,
                f"/services/{SERVICE_ID}/secret-files/smtp.env",
                {"name": "smtp.env", "content": secret_body},
            )
            print("  OK secret smtp.env")
        except urllib.error.HTTPError as exc:
            print(f"  aviso secret file: HTTP {exc.code}")

        hook = env.get("RENDER_DEPLOY_HOOK", "").strip()
        if hook:
            urllib.request.urlopen(urllib.request.Request(hook, method="POST"), timeout=30)
            print("  deploy hook OK")
        try:
            render_post(render_key, f"/services/{SERVICE_ID}/deploys")
            print("  deploy API OK")
        except urllib.error.HTTPError as exc:
            print(f"  aviso deploy API: HTTP {exc.code}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        print(f"ERROR Render HTTP {exc.code}: {body}")
        return 1

    print("Esperando email_enabled en producción...")
    if wait_health():
        print("CORREO ACTIVO EN PRODUCCIÓN.")
        return 0
    print("Variables guardadas; revisa Manual Deploy en Render si /health sigue en false.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
