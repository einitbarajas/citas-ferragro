# Plan de pruebas — Ferragro Citas

## 1. Alcance

| Capa | Qué se valida |
|------|----------------|
| PostgreSQL | Funciones PL/pgSQL en `db/database-crud/` |
| Backend | Reglas de negocio (logística, citas, bodegas) |
| API HTTP | Contrato JSON, auth, endpoints (manual / Locust) |
| Frontend | Build, accesibilidad (eslint jsx-a11y), flujos manuales |

---

## 2. Prerrequisitos

- Base local `db_trabajo` con esquema completo:

```powershell
cd "c:\dev\trabajo ferragro\db"
.\run-database-all.ps1
```

Incluye `init/001` … `014` (bodegas), `015` (índices) y todas las funciones CRUD.

- `.env` en la raíz con `DATABASE_URL` válido.
- Venv del backend: `backend\.venv` con `requirements.txt` instalado.

---

## 3. Pruebas automatizadas (pytest)

### 3.1 Funciones CRUD en PostgreSQL

```powershell
cd "c:\dev\trabajo ferragro\backend"
.\.venv\Scripts\python.exe -m pytest tests/test_db_crud_functions.py -v
```

| Suite | Casos | Notas |
|-------|-------|-------|
| Rol, credenciales, usuarios, proveedores | 7 | Transacción con rollback por test |
| Citas + historial | 5 | `citas_create` requiere **IdBodega** (6º parámetro o default en función) |

Si falla `IdBodega` nulo: reaplicar CRUD:

```powershell
cd db
.\run-database-crud.ps1
```

### 3.2 Reglas de logística (sin BD)

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_logistics_business_rules.py -v
```

Valida límites de acciones de Logística sobre citas (mocks, sin PostgreSQL).

### 3.3 Servicio de citas y franjas (unitarias)

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_appointment_service_unit.py tests/test_appointment_windows_unit.py -v
```

Anticipación mínima, extensión sin solape, throttle de `finalize`, duración de turnos.

### 3.4 Conflictos de horario y bodega (integración SQLAlchemy)

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_appointment_service_db.py -v
```

Requiere al menos una **bodega activa** y un **proveedor** en la BD (seed o tests CRUD previos).

### 3.5 API smoke

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_api_health.py -v
```

`/health` y esquema OpenAPI (sin PostgreSQL).

### 3.6 Todas las pruebas backend

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

Resumen típico: **~40 tests** (12 CRUD + 12 logística + unitarias + integración + health).

---

## 4. Prueba de carga (Locust)

Solo desarrollo/CI; desactivar rate limit:

```powershell
$env:RATE_LIMIT_ENABLED = "false"
pip install -r backend/requirements-dev.txt
cd backend
locust -f load_tests/locustfile.py --host=http://127.0.0.1:8000
```

Workflow manual en GitHub: **Load test (Locust)**.

Variables opcionales para escenarios con login: `STRESS_LOGIN_EMAIL`, `STRESS_LOGIN_PASSWORD`.

---

## 5. Frontend

```powershell
cd frontend
npm ci
npm run build
npm run lint:a11y
```

En desarrollo, axe-core puede activarse vía `frontend/src/axe.js`.

---

## 6. Pruebas manuales (checklist release)

| # | Escenario | Rol |
|---|-----------|-----|
| 1 | Login Admin | Admin |
| 2 | Crear proveedor / usuario Logística | Admin |
| 3 | Registro proveedor público | Visitante |
| 4 | Agendar cita eligiendo **bodega** y turno | Proveedor |
| 5 | Segundo proveedor mismo turno misma bodega → rechazo (409) | Proveedor |
| 6 | Cambiar estado / reprogramar cita | Logística |
| 7 | Recuperar contraseña (SMTP) | Cualquiera |
| 8 | `/health` en producción con `email_enabled: true` | — |

Producción: esperar cold start del API (~1 min) en la primera visita del día.

---

## 7. Criterios de salida

- `pytest tests/` en verde en local.
- `npm run build` sin errores.
- Migraciones SQL aplicadas en BD destino antes del deploy del API.
- `GET /health` con `build_id` esperado tras deploy.

---

*Última actualización: mayo 2026 (bodegas, citas_create, init 015).*
