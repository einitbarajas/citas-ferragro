"""Comprobaciones rápidas de sistema (BD + rutas API sin auth)."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.db.session import SessionLocal
from app.main import app
from app.models.warehouse import Warehouse


def main() -> None:
    db = SessionLocal()
    try:
        wh = db.execute(
            select(Warehouse.id).where(Warehouse.active.is_(True)).order_by(Warehouse.id).limit(1)
        ).scalar_one_or_none()
        teams = db.execute(
            text(
                """
                SELECT e."Id", e."IdBodega", e."Nombre"
                FROM "EquiposDescargaBodega" e
                WHERE e."Activo" = TRUE
                ORDER BY e."Id"
                LIMIT 5
                """
            )
        ).fetchall()
        bodegas = db.execute(text('SELECT COUNT(*) FROM "Bodegas" WHERE "Activa" = TRUE')).scalar()
        equipos = db.execute(text('SELECT COUNT(*) FROM "EquiposDescargaBodega" WHERE "Activo" = TRUE')).scalar()
        citas = db.execute(text('SELECT COUNT(*) FROM "Citas"')).scalar()
    finally:
        db.close()

    client = TestClient(app)
    lines = [
        f"Bodegas activas: {bodegas}",
        f"Equipos descarga activos: {equipos}",
        f"Citas totales: {citas}",
        f"GET /health -> {client.get('/health').status_code}",
        f"GET /openapi.json -> {client.get('/openapi.json').status_code}",
    ]
    if wh:
        lines.append(f"GET warehouses (sin token) -> {client.get('/api/v1/crud/warehouses').status_code} (esperado 401/403)")
        lines.append(
            f"GET franjas resumen bodega {wh} -> "
            f"{client.get(f'/api/v1/crud/appointment-franjas/fecha/resumen?year=2026&month=5&warehouse_id={wh}').status_code}"
        )
    if teams:
        tid, tb, tname = teams[0]
        lines.append(f"Equipo ejemplo: id={tid} bodega={tb} nombre={tname}")
        if wh:
            ok = client.get(
                f"/api/v1/crud/appointment-franjas?warehouse_id={wh}&unload_team_id={tid}"
            )
            bad = client.get(
                f"/api/v1/crud/appointment-franjas?warehouse_id={wh}&unload_team_id={tid}"
                if tb != wh
                else f"/api/v1/crud/appointment-franjas?warehouse_id={wh + 99}&unload_team_id={tid}"
            )
            lines.append(f"GET franjas equipo en su bodega -> {ok.status_code} (401 sin login)")
    for line in lines:
        print(line)


if __name__ == "__main__":
    main()
