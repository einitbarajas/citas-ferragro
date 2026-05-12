"""
Pruebas de carga / estrés para la API Ferragro (FastAPI).

Uso (desde la carpeta `backend`, con el servidor ya levantado):

  1) En el mismo entorno donde corre la API, desactiva rate limit solo para la prueba:
     PowerShell:  $env:RATE_LIMIT_ENABLED="false"
     cmd:         set RATE_LIMIT_ENABLED=false

  2) Instala dependencias de desarrollo (app + Locust):
     pip install -r requirements-dev.txt
     # (equivalente: pip install -r load_tests/requirements.txt)

  3) Opcional — usuario real para medir GET /api/appointments con JWT:
     $env:STRESS_LOGIN_EMAIL="tu@correo.com"
     $env:STRESS_LOGIN_PASSWORD="tu_clave"

  4) Interfaz web (recomendado la primera vez):
     locust -f load_tests/locustfile.py --host=http://127.0.0.1:8000

  5) Solo consola (ejemplo 30 usuarios, subida 5/s, 15 s):
     locust -f load_tests/locustfile.py --host=http://127.0.0.1:8000 ^
       --headless -u 30 -r 5 -t 15s

Sin STRESS_LOGIN_EMAIL / STRESS_LOGIN_PASSWORD, solo se ejecutan tareas sobre /health.

Tras una ronda muy agresiva sin desactivar rate limit, espera ~1 min o reinicia el API
antes de volver a probar (la cuota por IP es compartida).

Modo agresivo (solo si en el servidor pusiste RATE_LIMIT_ENABLED=false):
  $env:STRESS_AGGRESSIVE="1"
"""

from __future__ import annotations

import os

from locust import HttpUser, between, task
from locust.exception import StopUser


def _aggressive() -> bool:
    return os.environ.get("STRESS_AGGRESSIVE", "").strip().lower() in ("1", "true", "yes", "on")


class HealthUser(HttpUser):
    """Presión al /health. Por defecto pausa ~0.5–1.1s para no chocar con rate limit (120/min por IP)."""

    weight = 4
    wait_time = between(0.02, 0.08) if _aggressive() else between(0.55, 1.1)

    @task
    def health(self) -> None:
        self.client.get("/health", name="GET /health")


class AuthenticatedAppointmentsUser(HttpUser):
    """Simula proveedor/staff: login una vez y luego listado de citas."""

    weight = 1
    wait_time = between(0.1, 0.35)

    def on_start(self) -> None:
        email = os.environ.get("STRESS_LOGIN_EMAIL", "").strip()
        password = os.environ.get("STRESS_LOGIN_PASSWORD", "").strip()
        if not email or not password:
            raise StopUser()

        resp = self.client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
            name="POST /api/auth/login",
        )
        if resp.status_code != 200:
            raise StopUser()
        body = resp.json()
        if not body.get("success") or not body.get("data"):
            raise StopUser()
        token = body["data"].get("access_token")
        if not token:
            raise StopUser()
        self._token = token  # type: ignore[attr-defined]

    @task
    def list_appointments(self) -> None:
        token = getattr(self, "_token", None)
        if not token:
            return
        self.client.get(
            "/api/appointments",
            params={"mode": "list", "page": 1, "page_size": 25},
            headers={"Authorization": f"Bearer {token}"},
            name="GET /api/appointments?mode=list",
        )
