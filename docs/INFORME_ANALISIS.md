# Informe de análisis — Ferragro Citas

## Contexto

Ferragro requiere centralizar el agendamiento de entregas de materiales por proveedores externos, con supervisión de personal interno (Admin y Logística) y trazabilidad de cambios.

## Problema

- Coordinación manual de citas (correo, llamadas) sin visibilidad unificada.
- Riesgo de solapamiento de entregas en la misma ventana horaria.
- Falta de auditoría sobre quién modificó estados o horarios.

## Solución propuesta

Portal web + API REST + PostgreSQL:

- Autenticación unificada por correo con roles.
- Citas ligadas a **bodega**, franja horaria y proveedor.
- Validación de anticipación mínima y conflictos por bodega.
- Notificaciones en app y correo (SMTP).

## Arquitectura de despliegue

| Capa | Tecnología |
|------|------------|
| Frontend | React + Vite → Vercel |
| Backend | FastAPI → Render |
| Datos | PostgreSQL → Render |

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| Cold start Render Free | `warmApi()`, timeout 35 s en cliente, plan pago opcional |
| Pérdida de datos | Backups `pg_dump` (ver `operacion_continuidad.md`) |
| Drift esquema SQL | `run-database-all` + `run-database-crud` documentados |

## Conclusión

El sistema cubre el flujo principal de agendamiento y operación logística. Mantener pruebas automatizadas (`docs/PRUEBAS.md`) y guía de operación actualizada reduce regresiones en producción.

---

*Mayo 2026 — alinear con `INFORME DE ANALISIS.docx` en entregables.*
