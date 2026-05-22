"""Resolución de muelle por bodega (IDs ajenos en lecturas)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api.crud import _resolve_franja_unload_team_id
from app.models.warehouse import Warehouse
from app.services.unload_teams import list_active_unload_teams, resolve_unload_team_id_for_warehouse


def _first_warehouse_with_teams(db_session):
    wid = db_session.execute(
        select(Warehouse.id).where(Warehouse.active.is_(True)).order_by(Warehouse.id).limit(1)
    ).scalar_one_or_none()
    if wid is None:
        pytest.skip("Sin bodega activa")
    teams = list_active_unload_teams(db_session, int(wid))
    if not teams:
        pytest.skip("Sin equipos de descarga")
    return int(wid), teams[0]


def test_resolve_unload_team_coerces_invalid_id_on_read(db_session):
    wid, first_team = _first_warehouse_with_teams(db_session)
    resolved = resolve_unload_team_id_for_warehouse(db_session, wid, 999_999_999, strict=False)
    assert resolved == first_team.id


def test_resolve_unload_team_strict_raises_invalid_id(db_session):
    wid, _ = _first_warehouse_with_teams(db_session)
    with pytest.raises(HTTPException) as exc:
        resolve_unload_team_id_for_warehouse(db_session, wid, 999_999_999, strict=True)
    assert exc.value.status_code == 400


def test_resolve_franja_unload_team_coerces_stale_id(db_session):
    wid, first_team = _first_warehouse_with_teams(db_session)
    resolved = _resolve_franja_unload_team_id(db_session, wid, 999_999_999, required=False)
    assert resolved == first_team.id
