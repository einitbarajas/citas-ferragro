# Informe de análisis — Ferragro Citas

## 1. Contexto

Ferragro necesita centralizar el agendamiento de entregas de materiales por proveedores externos, con supervisión del personal interno y trazabilidad de cambios. El portal **Ferragro Citas** cubre bodegas con **múltiples muelles (equipos de descarga)**, franjas horarias configurables y operación en producción sobre **Vercel + Render**.

**Actores**

| Rol | Función |
|-----|---------|
| **Proveedor** | Registro, agendamiento y consulta de sus citas |
| **Logística** | Revisión, reprogramación, extensión y cierre operativo |
| **Admin** | Administración global, usuarios, bodegas, auditoría |
| **AdminBodega** | Misma operación que logística, limitada a bodegas asignadas |

**Entornos de referencia**

| Recurso | URL |
|---------|-----|
| Frontend (producción) | https://frontend-ferragro.vercel.app |
| API (producción) | https://ferragro-api.onrender.com |
| Health / versión | https://ferragro-api.onrender.com/health |
| Repositorio | https://github.com/einitbarajas/citas-ferragro |

---

## 2. Problema identificado

- Coordinación manual de citas (correo, llamadas) sin visibilidad unificada por bodega y muelle.
- Riesgo de solapamiento de entregas en la misma ventana horaria y en el mismo equipo de descarga.
- Falta de auditoría sobre quién modificó estados, duración u horarios.
- Dificultad para notificar a proveedores y staff ante cambios o recordatorios.
- Esquema de datos y reglas de negocio repartidos entre aplicación y funciones PL/pgSQL, con riesgo de **drift** si no se aplican migraciones documentadas.

---

## 3. Solución implementada

Portal web (React + Vite) + API REST (FastAPI) + PostgreSQL:

- **Autenticación** unificada por correo (JWT + refresh en cookie HttpOnly).
- **Citas** ligadas a bodega, **equipo de descarga (muelle)**, franja horaria y proveedor.
- **Validaciones**: anticipación mínima para agendar/reprogramar, cancelación con aviso mínimo, conflictos por muelle, zona horaria de negocio (`America/Bogota`).
- **Notificaciones** in-app (`/api/v1/notifications`) y por correo (SMTP único configurable con `SMTP_PROFILE`).
- **Schedulers** en el API: recordatorios, marca automática **no presentada**, purga de notificaciones antiguas y purga de proveedores suspendidos.
- **Auditoría**: historial de cambios en citas y eventos administrativos.

---

## 4. Arquitectura lógica

```txt
[Proveedor / Staff] → Frontend (Vercel)
        ↓ HTTPS + Bearer JWT
    API FastAPI (Render) ──→ SMTP (Office365 / Gmail)
        ↓
    PostgreSQL (Render) ← PL/pgSQL (db/database-crud/)
```

| Capa | Tecnología | Responsabilidad |
|------|------------|-----------------|
| Presentación | React, Vite, Tailwind | Login, dashboard por rol, calendario, notificaciones |
| API | FastAPI, Pydantic, SQLAlchemy | Auth, CRUD citas/bodegas/franjas, notificaciones, admin |
| Datos | PostgreSQL 12+ | Tablas en español, triggers de auditoría, funciones CRUD |
| Integración | SMTP, Cloudinary (opcional) | Correos y fotos de perfil |

**Migraciones**: scripts `db/init/001` … `023` + `run-database-crud.ps1`; orquestación `db/run-database-all.ps1`.

---

## 5. Análisis por módulo

| Módulo | Estado | Observaciones |
|--------|--------|---------------|
| Auth / sesiones | Implementado | Login, refresh, logout, recuperación de contraseña (requiere SMTP en prod) |
| Citas y franjas | Implementado | Cupos por muelle; legacy `/api/appointments` y contrato `/api/crud` |
| Bodegas y equipos | Implementado | Nombres de muelle; integridad `021` |
| Roles y alcance | Implementado | `AdminBodega` + `UsuariosBodegas` |
| Notificaciones | Implementado | Campana UI + emails asíncronos |
| Analítica / reportes | Implementado | Rangos día/semana/mes/quincena; TZ Bogotá |
| CI/CD | Implementado | GitHub Actions: pytest sin/con BD + build frontend |
| Pruebas E2E UI | Pendiente | Playwright no automatizado; checklist manual en `PRUEBAS.md` |

---

## 6. Calidad y pruebas

| Tipo | Cobertura actual |
|------|------------------|
| **pytest** | **85 tests** en 15 archivos (`backend/tests/`) |
| Sin PostgreSQL | 54 (unitarios, smoke API, reglas logística, correo) |
| Con PostgreSQL | 31 (CRUD SQL, citas, muelles, analítica TZ) |
| **CI** | `.github/workflows/ci.yml` en cada push/PR a `main` |
| **Manual** | 13 escenarios release en `docs/PRUEBAS.md` / `PRUEBAS.docx` §6 |
| **Detalle por test** | 85 fichas en `PRUEBAS.docx` §8 |

Comando local: `cd backend` → `pytest tests/ -v` (con `DATABASE_URL` y esquema aplicado).

---

## 7. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Cold start Render (plan Free) | Primera petición lenta (~30–90 s) | `warmApi()` en cliente; checklist `PASOS-ENTRAR-PORTAL.md` |
| SMTP no configurado en prod | Sin correos ni recuperación de clave | Variables en Render; aviso en `/health` (`email_enabled`) |
| Drift esquema SQL | Errores en CRUD o citas | `run-database-all.ps1`, migraciones `016`–`023` documentadas |
| Pérdida de datos | Interrupción operativa | Backups `pg_dump` (`docs/operacion_continuidad.docx`) |
| Regresiones en despliegue | API desactualizado vs Git | Verificar `build_id` en `/health` tras deploy |
| Rate limit / abuso | Bloqueo de login | `RATE_LIMIT_ENABLED`, política de intentos en config |

---

## 8. Conclusión

El sistema **cubre el flujo principal** de agendamiento y operación logística en bodegas Ferragro: múltiples muelles, roles incluido **AdminBodega**, cierre automático por **no presentada**, notificaciones multicanal y suite de **85 pruebas automatizadas** con CI. La documentación operativa (`GUIA_OPERACION_PRODUCCION.docx`, `PRUEBAS.docx`, `README.md`) debe mantenerse alineada con cada release.

**Recomendaciones**

1. Tras cada release: comprobar `/health` (`build_id` actual) y ejecutar checklist manual §6 de pruebas.
2. Aplicar migraciones pendientes en BD de producción antes de desplegar API.
3. Completar trazabilidad requisitos ↔ pruebas en `MATRIZ_TRAZABILIDAD_FERRAGRO.xlsx`.
4. Valorar E2E (Playwright) para flujos críticos de proveedor y logística.

---

**Nota para el informe Word (`INFORME DE ANALISIS.docx`):** diagramas, capturas de pantalla y mockups deben insertarse o actualizarse manualmente en Word; este `.md` es el resumen ejecutivo regenerable.

---

*Última actualización: 26 mayo 2026 — roles AdminBodega, muelles, notificaciones, schedulers, 85 tests pytest, CI, migraciones BD hasta `023`.*
