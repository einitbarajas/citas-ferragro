# Evidencia de cumplimiento de requerimientos (referencia técnica)

Resumen de **dónde** quedó implementada cada línea principal del plan (código + documentación operativa).

## Backend

| Tema | Ubicación |
|------|-----------|
| API versionada `/api` y `/api/v1` | `backend/app/main.py` |
| Sesiones refresh con JTI + invalidación por logout / logout-all | `backend/app/api/auth.py`, `backend/app/services/auth_sessions.py`, `db/init/011_auth_sessions_login_audit.sql` |
| Bloqueo por intentos fallidos | `backend/app/services/login_policy.py`, `backend/app/api/auth.py` |
| Auditoría login | tabla `AuditoriaLogin`, escritura en `auth.py` |
| Listado citas: filtros estado/proveedor, paginación | `backend/app/api/appointments.py`, `backend/app/api/crud.py` |
| Export CSV citas | `GET .../crud/appointments/export.csv` en `crud.py` |
| Recordatorios (scheduler) | `backend/app/services/reminder_scheduler.py`, tabla `EjecucionesRecordatorio` |
| `/health` | `backend/app/main.py` |
| Trazabilidad old/new en historial | columnas en `HistorialCambios`, escritura en `appointments.py` y `crud.py` |
| Anticipación mínima configurable (48 h por defecto) | `settings.appointment_minimum_notice_hours`, `appointments.py`, `core/config.py` |
| Conflicto horario (check) | `GET .../appointments/conflict-check`, `appointment_service.slot_conflict_check` |
| Rate limiting + correlación | `slowapi` en `main.py`, cabecera `X-Correlation-ID` |

## Frontend

| Tema | Ubicación |
|------|-----------|
| Prefijo API `VITE_API_PREFIX` (default `/api/v1`) | `frontend/src/api/client.js`, páginas |
| Lazy loading rutas/páginas | `frontend/src/App.jsx` (`React.lazy`) |
| Modal confirmación | `frontend/src/components/ConfirmDialog.jsx` |
| CSV desde UI | botón en `DashboardPage.jsx` → export blob |
| Borrador formulario cita (localStorage) | `frontend/src/components/AppointmentForm.jsx` |
| Historial por cita (filtro ID) | campo ID cita en auditoría + query `appointment_id` |

## Base de datos / operación

| Tema | Ubicación |
|------|-----------|
| Scripts nuevos | `db/init/011_auth_sessions_login_audit.sql`, `012_db_roles_template.sql` |
| Orquestación | `db/run-database-all.ps1` |
| RPO/RTO, backups, roles | `documentacion/operacion_continuidad.md` |

## Notas / límites conscientes

- **Duplicar cita** como acción dedicada en UI no está cableada (se puede volver a crear manualmente copiando datos).
- **Indicador de conflicto en tiempo real** en el formulario del proveedor: existe endpoint `GET /appointments/conflict-check`; falta integración visual completa en `AppointmentForm` del flujo proveedor si se desea el mismo nivel que en admin.
- **i18n exhaustiva**: no hay catálogo multi-idioma completo; la base está preparada para textos en español y variables de entorno documentadas.
- **Particionamiento físico de tablas** y **jobs de archivo histórico**: descritos en `operacion_continuidad.md`; la aplicación en EE.XX lo debe ejecutar el equipo de operaciones según volumetría.
- **SLO de rendimiento** (<500 ms API, <2 s carga web): requiere medición en el entorno objetivo (no automatizada en el repo).
