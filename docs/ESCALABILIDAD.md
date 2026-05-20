# Escalabilidad Ferragro (1000+ usuarios)

## Por qué puede sentirse lenta hoy

1. **Muchas peticiones al abrir el panel**: citas, recordatorios, notificaciones, bodegas, perfil, etc. a la vez.
2. **Actualización automática cada 45 s** (antes 15 s) mientras la pestaña está visible.
3. **Reprogramar cita** hacía una petición por cada turno; ahora usa un solo `GET /appointments/available-slots`.
4. **Listar citas en modo “lista completa”** trae muchos registros; conviene filtrar por semana/mes/día.
5. **`finalize_elapsed`** en cada listado (ahora limitado a 1 vez por minuto).

## Conflictos de horario (dos personas al mismo turno)

El backend ya evita doble reserva con:

- **`pg_advisory_xact_lock`** por bodega + minuto de inicio al guardar.
- **Comprobación de solapamiento** por bodega antes de confirmar.

No hace falta que el usuario “elija rápido”: el segundo recibe error 409 y debe elegir otro turno.

## Cambios aplicados en código

| Área | Mejora |
|------|--------|
| Reprogramación (staff) | 1 petición `available-slots` en lugar de N `conflict-check` |
| Reserva de turno | Consulta acotada por ventana horaria (no todas las citas de la bodega) |
| Listado citas (staff) | Por defecto carga **semana** (`mode=week`), máx. 100 por página |
| Auto-refresh | 45 s y solo si la pestaña está visible |
| Historial logística | Ya no se carga al entrar; solo en pestaña Historial |
| Finalizar citas vencidas | Máximo 1 ejecución por minuto |
| BD | Índices en `015_performance_indexes.sql` |

Ejecutar en PostgreSQL (una vez):

```powershell
psql $env:DATABASE_URL -f db/init/015_performance_indexes.sql
```

## Capacidad orientativa

| Escenario | Infra mínima recomendada |
|-----------|---------------------------|
| ~100 usuarios activos a la vez | 1 API + 1 PostgreSQL (4 CPU, 8 GB RAM) |
| ~1000 usuarios registrados, ~50–150 concurrentes | API con 2–4 workers (gunicorn/uvicorn), PostgreSQL dedicado, connection pool 20–50 |
| Picos fuertes (todos agendan a las 8:00) | Cola Redis + rate limit por IP; CDN para frontend estático |

## Producción recomendada

1. **Frontend**: build estático (`npm run build`) en Nginx o CDN; no servir con Vite dev.
2. **API**: varios workers, no un solo `py main.py`:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
   ```
3. **PostgreSQL**: `max_connections` acorde al pool; backups diarios.
4. **Variables** (`.env`): `RATE_LIMIT_ENABLED=true` en producción; desactivar solo en pruebas Locust.
5. **Prueba de carga** (local):
   ```powershell
   $env:RATE_LIMIT_ENABLED="false"
   pip install -r backend/requirements-dev.txt
   locust -f backend/load_tests/locustfile.py --host=http://127.0.0.1:8000
   ```

## Uso diario para que vaya más rápido

- En **Citas**, usar vista **Por día** o **Por semana**, no “lista (todas)”.
- Filtrar por **bodega** cuando aplique.
- Cerrar el modal de cita al terminar (evita recargas de turnos).
- No dejar muchas pestañas del portal abiertas (cada una hace polling).

## Si aún crece el tráfico

- Redis para caché de franjas del día (TTL 1–5 min).
- Separar lecturas (réplica PostgreSQL) para reportes.
- WebSockets o SSE solo para notificaciones, en lugar de polling.
