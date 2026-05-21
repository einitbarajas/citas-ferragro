"""Verificación operativa: esquema BD, CRUD citas, constraints franjas, API viva."""
from __future__ import annotations

import os
import sys

import httpx
from sqlalchemy import text

from app.db.session import SessionLocal

FAIL = 1
OK = 0


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    global _had_fail
    _had_fail = True


_had_fail = False


def _ok(msg: str) -> None:
    print(f"OK: {msg}")


def check_column(db, table: str, column: str) -> bool:
    n = db.execute(
        text(
            """
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = :t AND column_name = :c
            """
        ),
        {"t": table, "c": column},
    ).scalar()
    return int(n or 0) > 0


def check_table(db, table: str) -> bool:
    n = db.execute(
        text(
            """
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = :t
            """
        ),
        {"t": table},
    ).scalar()
    return int(n or 0) > 0


def main() -> int:
    global _had_fail
    db = SessionLocal()
    try:
        if not check_table(db, "EquiposDescargaBodega"):
            _fail('Tabla "EquiposDescargaBodega" no existe (migración 016)')
        else:
            _ok("Tabla EquiposDescargaBodega")

        for col, tbl in [
            ("IdEquipoDescargaBodega", "Citas"),
            ("IdEquipoDescargaBodega", "FranjasPermitidasCitaFecha"),
            ("IdEquipoDescargaBodega", "FranjasPermitidasCita"),
            ("EquiposDescarga", "Bodegas"),
            ("EquiposDescarga", "Proveedores"),
        ]:
            if not check_column(db, tbl, col):
                _fail(f'Columna "{tbl}"."{col}" ausente')
            else:
                _ok(f'Columna {tbl}.{col}')

        legacy = db.execute(
            text(
                """
                SELECT 1 FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                WHERE t.relname = 'FranjasPermitidasCitaFecha'
                  AND c.conname = 'UqFranjaFechaBodegaOrden'
                """
            )
        ).scalar()
        if legacy:
            _fail("Constraint legacy UqFranjaFechaBodegaOrden aún existe (ejecutar fix_franjas_constraint.py)")
        else:
            _ok("Sin constraint legacy UqFranjaFechaBodegaOrden")

        for tbl, expected in [
            ("FranjasPermitidasCitaFecha", "UqFranjaFechaBodegaEquipoOrden"),
            ("FranjasPermitidasCita", "UqFranjaBodegaEquipoOrden"),
        ]:
            has = db.execute(
                text(
                    """
                    SELECT COUNT(*) FROM pg_indexes
                    WHERE tablename = :t AND indexname = :i
                    """
                ),
                {"t": tbl, "i": expected},
            ).scalar()
            if int(has or 0) < 1:
                _fail(f'Falta índice "{expected}" en {tbl} (migración 018/019)')
            else:
                _ok(f'Índice {expected} en {tbl}')

        bodegas = db.execute(text('SELECT COUNT(*) FROM "Bodegas" WHERE "Activa" = TRUE')).scalar() or 0
        equipos = db.execute(text('SELECT COUNT(*) FROM "EquiposDescargaBodega" WHERE "Activo" = TRUE')).scalar() or 0
        if int(bodegas) > 0 and int(equipos) < 1:
            _fail("Hay bodegas activas pero ningún equipo de descarga (016/seed)")
        else:
            _ok(f"Bodegas activas={bodegas}, equipos activos={equipos}")

        sin_equipo = db.execute(
            text(
                """
                SELECT COUNT(*) FROM "Citas" c
                WHERE c."IdEquipoDescargaBodega" IS NULL
                """
            )
        ).scalar() or 0
        if int(sin_equipo) > 0:
            _fail(f'{sin_equipo} citas sin IdEquipoDescargaBodega')
        else:
            _ok("Todas las citas tienen equipo asignado")

        fn = db.execute(
            text(
                """
                SELECT pg_get_function_identity_arguments(p.oid)
                FROM pg_proc p
                JOIN pg_namespace n ON p.pronamespace = n.oid
                WHERE n.nspname = 'public' AND p.proname = 'citas_create'
                ORDER BY p.oid DESC
                LIMIT 1
                """
            )
        ).scalar() or ""
        if "p_id_equipo_descarga" not in (fn or ""):
            _fail(f"citas_create sin p_id_equipo_descarga (redeploy CRUD). Args: {fn}")
        else:
            _ok("Función citas_create con parámetros de equipo")

    finally:
        db.close()

    base = (os.environ.get("OPERATIONAL_API_BASE") or "http://127.0.0.1:8000").rstrip("/")
    try:
        r = httpx.get(f"{base}/health", timeout=5.0)
        if r.status_code == 200:
            _ok(f"API viva GET {base}/health -> 200")
        else:
            _fail(f"GET {base}/health -> {r.status_code}")
    except httpx.HTTPError as e:
        _fail(f"API no alcanzable en {base}: {e}")

    login_email = os.environ.get("OPERATIONAL_LOGIN_EMAIL", "").strip()
    login_password = os.environ.get("OPERATIONAL_LOGIN_PASSWORD", "").strip()
    if login_email and login_password:
        try:
            login = httpx.post(
                f"{base}/api/v1/auth/login",
                json={"email": login_email, "password": login_password},
                timeout=10.0,
            )
            if login.status_code != 200:
                _fail(f"Login operacional -> {login.status_code}")
            else:
                token = login.json().get("access_token") or login.json().get("data", {}).get("access_token")
                if not token:
                    _fail("Login OK pero sin access_token en respuesta")
                else:
                    headers = {"Authorization": f"Bearer {token}"}
                    wh_r = httpx.get(f"{base}/api/v1/crud/warehouses", headers=headers, timeout=10.0)
                    if wh_r.status_code != 200:
                        _fail(f"GET warehouses autenticado -> {wh_r.status_code}")
                    else:
                        wh_list = wh_r.json().get("data") or wh_r.json()
                        wid = wh_list[0]["id"] if isinstance(wh_list, list) and wh_list else None
                        _ok("Login y GET warehouses autenticado")
                        if wid:
                            teams = httpx.get(
                                f"{base}/api/v1/appointments/unload-teams?warehouse_id={wid}",
                                headers=headers,
                                timeout=10.0,
                            )
                            resumen = httpx.get(
                                f"{base}/api/v1/crud/appointment-franjas/fecha/resumen"
                                f"?year=2026&month=5&warehouse_id={wid}",
                                headers=headers,
                                timeout=10.0,
                            )
                            if teams.status_code != 200:
                                _fail(f"GET unload-teams -> {teams.status_code}")
                            elif resumen.status_code != 200:
                                _fail(f"GET franjas resumen -> {resumen.status_code}")
                            else:
                                _ok("unload-teams y resumen mensual autenticados")
        except httpx.HTTPError as e:
            _fail(f"Prueba autenticada falló: {e}")
    else:
        print("INFO: Sin OPERATIONAL_LOGIN_EMAIL/PASSWORD; omitida prueba autenticada (opcional).")

    if _had_fail:
        print("\nResultado: NO operativo al 100% — corregir ítems FAIL arriba.")
        return FAIL
    print("\nResultado: operativo al 100% (esquema + API). Prueba manual UI recomendada.")
    return OK


if __name__ == "__main__":
    sys.exit(main())
