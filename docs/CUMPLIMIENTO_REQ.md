# Cumplimiento de requisitos — Resumen

Documento de seguimiento frente a `ESPECIFICACION_REQUISITOS_IEEE830_FERRAGRO.docx` y `req_trabajo.xlsx`.

---

## Estado general (mayo 2026)

| Área | Estado | Evidencia |
|------|--------|-----------|
| Auth JWT + refresh cookie | Implementado | `backend/app/api/auth.py`, pruebas manuales |
| Roles Admin / Logística / Proveedor | Implementado | Panel por rol |
| Citas con anticipación y conflictos | Implementado | `appointment_service.py`, 409 por solapamiento |
| **Bodegas en citas** | Implementado | `014`, modelos, UI selector de bodega |
| Franjas por bodega y fecha | Implementado | `014`, `009`, API appointments |
| SMTP / recuperación contraseña | Implementado (requiere env en Render) | `/health` → `email_enabled` |
| Auditoría historial | Implementado | Triggers `002`, tablas historial |
| Despliegue Vercel + Render | Operativo | Guía operación |
| Pruebas automatizadas BD | Implementado | `test_db_crud_functions.py` (12 tests) |
| Pruebas reglas logística | Implementado | `test_logistics_business_rules.py` |
| CI en cada PR | Implementado | `.github/workflows/ci.yml` (pytest sin BD, pytest+PostgreSQL, build Vite) |

---

## Requisitos recientes cubiertos

1. **RF bodega obligatoria**: toda cita persiste `IdBodega`; función `citas_create` actualizada.
2. **RNF rendimiento**: índices `015`, listado por semana, `available-slots` unificado (ver `ESCALABILIDAD.md`).
3. **RNF disponibilidad**: `/health` con `build_id` y flags SMTP.

---

## Brechas conocidas

| Tema | Notas |
|------|-------|
| Plan Free Render | Cold start 30–90 s; no es fallo de software |
| Alembic / versionado migraciones | Scripts `init/` manuales; tabla `schema_migrations` no implementada aún |
| E2E Playwright | No automatizado |
| Excel de trazabilidad | Actualizar `MATRIZ_TRAZABILIDAD_FERRAGRO.xlsx` manualmente tras cambios RF |

---

## Cómo actualizar este documento

1. Regenerar IEEE 830: `python docs/generate_ieee830.py`
2. Exportar requisitos: `python docs/_extract_req.py`
3. Revisar casos en [PRUEBAS.md](PRUEBAS.md)
4. Copiar resumen a `CUMPLIMIENTO_REQ.docx` si se entrega en Word

---

*Última actualización: mayo 2026.*
