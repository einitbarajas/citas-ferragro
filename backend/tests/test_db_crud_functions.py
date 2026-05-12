"""
Pruebas de integracion de las funciones PL/pgSQL en db/database-crud/ (por tabla).

Requisitos: base aplicada con run-database-all.ps1 (o al menos schema + CRUD functions).
Los cambios se revierten con ROLLBACK al cerrar cada prueba (fixture db).
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import pytest
import psycopg

# --- helpers ---


def _suffix() -> str:
    return uuid.uuid4().hex[:12]


def _scalar(cur, sql: str, params: tuple | None = None):
    cur.execute(sql, params or ())
    row = cur.fetchone()
    return row[0] if row else None


def _one(cur, sql: str, params: tuple | None = None):
    cur.execute(sql, params or ())
    return cur.fetchone()


def _all(cur, sql: str, params: tuple | None = None):
    cur.execute(sql, params or ())
    return cur.fetchall()


def _rol_logistica_id(cur) -> int:
    rid = _scalar(cur, 'SELECT "Id" FROM "Rol" WHERE "Nombre" = %s LIMIT 1', ("Logistica",))
    assert rid is not None, 'Debe existir el rol Logistica (seed o 001_schema)'
    return int(rid)


# --- Rol ---


def test_rol_crud(db):
    with db.cursor() as cur:
        name = f"__pytest_rol_{_suffix()}"
        rid = _scalar(cur, "SELECT rol_create(%s)", (name,))
        assert isinstance(rid, int) and rid > 0

        row = _one(cur, "SELECT * FROM rol_get_by_id(%s)", (rid,))
        assert row[0] == rid and row[1] == name

        new_name = name + "_upd"
        cur.execute("SELECT rol_update(%s, %s)", (rid, new_name))
        row = _one(cur, "SELECT * FROM rol_get_by_id(%s)", (rid,))
        assert row[1] == new_name

        rows = _all(cur, "SELECT * FROM rol_get_all()")
        ids = [r[0] for r in rows]
        assert rid in ids

        cur.execute("SELECT rol_delete(%s)", (rid,))


def test_rol_get_by_id_not_found(db):
    with db.cursor() as cur:
        with pytest.raises(psycopg.Error):
            _one(cur, "SELECT * FROM rol_get_by_id(%s)", (-999999,))


# --- Credenciales ---


def test_credenciales_crud(db):
    with db.cursor() as cur:
        email = f"pytest_cred_{_suffix()}@test.local"
        cid = _scalar(cur, "SELECT credenciales_create(%s, %s)", (email, "$2b$12$pytest_hash_placeholder"))
        assert isinstance(cid, int) and cid > 0

        row = _one(cur, "SELECT * FROM credenciales_get_by_id(%s)", (cid,))
        assert row[0] == cid and row[1] == email

        cur.execute("SELECT credenciales_update(%s, %s, %s)", (cid, email, "$2b$12$pytest_hash_updated"))
        row = _one(cur, "SELECT * FROM credenciales_get_by_id(%s)", (cid,))
        assert row[2] == "$2b$12$pytest_hash_updated"

        rows = _all(cur, "SELECT * FROM credenciales_get_all()")
        assert any(r[0] == cid for r in rows)

        cur.execute("SELECT credenciales_delete(%s)", (cid,))


def test_credenciales_create_plain_bcrypt_compatible(db):
    """pgcrypto crypt(gen_salt('bf')) debe coincidir con verificación bcrypt del API."""
    with db.cursor() as cur:
        email = f"pytest_plain_{_suffix()}@test.local"
        pwd = "PlainPwdForBcrypt12!"
        try:
            cid = _scalar(cur, "SELECT credenciales_create_plain(%s, %s)", (email, pwd))
        except psycopg.Error as exc:
            msg = str(exc).lower()
            if "credenciales_create_plain" in msg or "pgcrypto" in msg or "permission denied" in msg:
                pytest.skip("Aplica db/run-database-crud.ps1 y permisos CREATE EXTENSION pgcrypto")
            raise
        assert isinstance(cid, int) and cid > 0
        h = _scalar(cur, 'SELECT "HashContrasena" FROM "Credenciales" WHERE "IdCredencial" = %s', (cid,))
        assert isinstance(h, str) and h.startswith(("$2a$", "$2b$", "$2y$"))
        assert bcrypt.checkpw(pwd.encode("utf-8"), h.encode("utf-8"))
        cur.execute("SELECT credenciales_delete(%s)", (cid,))


# --- Usuarios ---


def test_usuarios_crud(db):
    with db.cursor() as cur:
        rid = _rol_logistica_id(cur)
        email = f"pytest_user_{_suffix()}@test.local"
        cid = _scalar(cur, "SELECT credenciales_create(%s, %s)", (email, "$2b$12$u"))
        doc = str(random.randint(10_000_000, 99_999_999))
        if len(doc) < 8:
            doc = doc.ljust(8, "1")

        out = _scalar(cur, "SELECT usuarios_create(%s, %s, %s, %s)", (doc, "Usuario Pytest CRUD", cid, rid))
        assert out == doc

        row = _one(cur, "SELECT * FROM usuarios_get_by_id(%s)", (doc,))
        assert row[0] == doc and row[1] == "Usuario Pytest CRUD" and row[3] == rid

        cur.execute(
            "SELECT usuarios_update(%s, %s, %s, %s)",
            (doc, "Usuario Pytest Actualizado", cid, rid),
        )
        row = _one(cur, "SELECT * FROM usuarios_get_by_id(%s)", (doc,))
        assert row[1] == "Usuario Pytest Actualizado"

        rows = _all(cur, "SELECT * FROM usuarios_get_all()")
        assert any(r[0] == doc for r in rows)

        cur.execute("SELECT usuarios_delete(%s)", (doc,))
        cur.execute("SELECT credenciales_delete(%s)", (cid,))


# --- Proveedores ---


def test_proveedores_crud(db):
    with db.cursor() as cur:
        email = f"pytest_prov_{_suffix()}@test.local"
        cid = _scalar(cur, "SELECT credenciales_create(%s, %s)", (email, "$2b$12$p"))
        nit = random.randint(800_123_456, 899_999_999)
        while _scalar(cur, 'SELECT 1 FROM "Proveedores" WHERE "IdNit" = %s', (nit,)):
            nit = random.randint(800_123_456, 899_999_999)

        cur.execute(
            "SELECT proveedores_create(%s, %s, %s, %s, %s, %s, %s)",
            (nit, "1", "Empresa Pytest", email, cid, "Contacto", "12345678"),
        )
        row = _one(cur, "SELECT * FROM proveedores_get_by_id(%s)", (nit,))
        assert row[0] == nit and row[2] == "Empresa Pytest" and row[3] == email

        cur.execute(
            "SELECT proveedores_update(%s, %s, %s, %s, %s, %s, %s)",
            (nit, "2", "Empresa Pytest Upd", email, cid, "Otro", "87654321"),
        )
        row = _one(cur, "SELECT * FROM proveedores_get_by_id(%s)", (nit,))
        assert row[1] == "2" and row[2] == "Empresa Pytest Upd"

        rows = _all(cur, "SELECT * FROM proveedores_get_all()")
        assert any(r[0] == nit for r in rows)

        cur.execute("SELECT proveedores_delete(%s)", (nit,))
        cur.execute("SELECT credenciales_delete(%s)", (cid,))


# --- Citas ---


def test_citas_crud_create_read_update(db):
    with db.cursor() as cur:
        email = f"pytest_cita_{_suffix()}@test.local"
        cid = _scalar(cur, "SELECT credenciales_create(%s, %s)", (email, "$2b$12$c"))
        nit = random.randint(801_000_000, 801_999_999)
        while _scalar(cur, 'SELECT 1 FROM "Proveedores" WHERE "IdNit" = %s', (nit,)):
            nit += 1
        cur.execute(
            "SELECT proveedores_create(%s, %s, %s, %s, %s, %s, %s)",
            (nit, "3", "Prov Cita", email, cid, "C", "11223344"),
        )

        start = datetime.now(timezone.utc) + timedelta(days=5)
        appt_id = _scalar(
            cur,
            "SELECT citas_create(%s, %s, %s, %s, %s)",
            (nit, "Material pytest", start, 90, "sin_revision"),
        )
        assert isinstance(appt_id, int)

        row = _one(cur, "SELECT * FROM citas_get_by_id(%s)", (appt_id,))
        assert row[0] == appt_id and row[1] == nit and "pytest" in row[2].lower()

        start2 = start + timedelta(hours=1)
        cur.execute(
            "SELECT citas_update(%s, %s, %s, %s, %s, %s)",
            (appt_id, nit, "Material pytest actualizado", start2, 120, "revisado"),
        )
        row = _one(cur, "SELECT * FROM citas_get_by_id(%s)", (appt_id,))
        assert row[2] == "Material pytest actualizado" and row[4] == 120

        rows = _all(cur, "SELECT * FROM citas_get_all()")
        assert any(r[0] == appt_id for r in rows)
        # Rollback del fixture elimina cita, proveedor y credencial de prueba.


def test_citas_delete_raises_when_historial_blocks(db):
    """Si el trigger inserto historial, citas_delete puede fallar por FK o dependencias."""
    with db.cursor() as cur:
        email = f"pytest_citadel_{_suffix()}@test.local"
        cred_id = _scalar(cur, "SELECT credenciales_create(%s, %s)", (email, "$2b$12$d"))
        nit = random.randint(802_000_000, 802_999_999)
        while _scalar(cur, 'SELECT 1 FROM "Proveedores" WHERE "IdNit" = %s', (nit,)):
            nit += 1
        cur.execute(
            "SELECT proveedores_create(%s, %s, %s, %s, %s, %s, %s)",
            (nit, "4", "Prov Del", email, cred_id, "D", "22334455"),
        )
        start = datetime.now(timezone.utc) + timedelta(days=6)
        appt_id = _scalar(
            cur,
            "SELECT citas_create(%s, %s, %s, %s, %s)",
            (nit, "Cita para delete", start, 60, "sin_revision"),
        )
        # Trigger de auditoria suele insertar en HistorialCambios
        n_hist = _scalar(cur, 'SELECT COUNT(*) FROM "HistorialCambios" WHERE "IdCita" = %s', (appt_id,))
        assert n_hist is not None and int(n_hist) >= 1

        with pytest.raises(psycopg.Error):
            cur.execute("SELECT citas_delete(%s)", (appt_id,))


# --- HistorialCambios ---


def test_historial_cambios_read(db):
    with db.cursor() as cur:
        rows = _all(cur, "SELECT * FROM historial_cambios_get_all()")
        assert isinstance(rows, list)


def test_historial_cambios_create_and_get_by_id(db):
    with db.cursor() as cur:
        email = f"pytest_hist_{_suffix()}@test.local"
        cred_id = _scalar(cur, "SELECT credenciales_create(%s, %s)", (email, "$2b$12$h"))
        nit = random.randint(803_000_000, 803_999_999)
        while _scalar(cur, 'SELECT 1 FROM "Proveedores" WHERE "IdNit" = %s', (nit,)):
            nit += 1
        cur.execute(
            "SELECT proveedores_create(%s, %s, %s, %s, %s, %s, %s)",
            (nit, "5", "Prov Hist", email, cred_id, "H", "33445566"),
        )
        start = datetime.now(timezone.utc) + timedelta(days=7)
        appt_id = _scalar(
            cur,
            "SELECT citas_create(%s, %s, %s, %s, %s)",
            (nit, "Cita hist", start, 90, "sin_revision"),
        )
        hid = _scalar(
            cur,
            "SELECT historial_cambios_create(%s, %s, %s, %s, %s)",
            ("12345678", appt_id, "pytest_action", "pytest desc", None),
        )
        assert isinstance(hid, int) and hid > 0

        row = _one(cur, "SELECT * FROM historial_cambios_get_by_id(%s)", (hid,))
        assert row[0] == hid and row[2] == appt_id
        # Sin borrar proveedor/cita (FK + historial): el fixture hace ROLLBACK.


def _create_cita_con_historial_por_trigger(cur) -> tuple[int, int]:
    """Devuelve (id_cita, id_historial) usando el trigger de 002_audit_triggers."""
    email = f"pytest_immut_{_suffix()}@test.local"
    cred_id = _scalar(cur, "SELECT credenciales_create(%s, %s)", (email, "$2b$12$i"))
    nit = random.randint(804_000_000, 804_999_999)
    while _scalar(cur, 'SELECT 1 FROM "Proveedores" WHERE "IdNit" = %s', (nit,)):
        nit += 1
    cur.execute(
        "SELECT proveedores_create(%s, %s, %s, %s, %s, %s, %s)",
        (nit, "6", "Prov Imm", email, cred_id, "I", "44556677"),
    )
    start = datetime.now(timezone.utc) + timedelta(days=8)
    appt_id = _scalar(
        cur,
        "SELECT citas_create(%s, %s, %s, %s, %s)",
        (nit, "Cita trigger historial", start, 90, "sin_revision"),
    )
    hid = _scalar(
        cur,
        'SELECT "Id" FROM "HistorialCambios" WHERE "IdCita" = %s ORDER BY "Id" DESC LIMIT 1',
        (appt_id,),
    )
    assert hid is not None
    return int(appt_id), int(hid)


def test_historial_cambios_update_immutable(db):
    with db.cursor() as cur:
        _appt_id, hid = _create_cita_con_historial_por_trigger(cur)
        row = _one(cur, "SELECT * FROM historial_cambios_get_by_id(%s)", (hid,))
        with pytest.raises(psycopg.Error) as exc:
            cur.execute(
                "SELECT historial_cambios_update(%s, %s, %s, %s, %s, %s)",
                (hid, row[1], row[2], row[3], row[4], row[5]),
            )
        assert "inmutable" in str(exc.value).lower()


def test_historial_cambios_delete_immutable(db):
    with db.cursor() as cur:
        _appt_id, hid = _create_cita_con_historial_por_trigger(cur)
        with pytest.raises(psycopg.Error) as exc:
            cur.execute("SELECT historial_cambios_delete(%s)", (hid,))
        assert "inmutable" in str(exc.value).lower() or "historial" in str(exc.value).lower()
