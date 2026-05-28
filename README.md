# Ferragro - Gestión de Citas de Entrega

Portal web para agendar y operar citas de entrega en bodegas Ferragro: proveedores, logística, administración global y **administradores de bodega** (alcance por bodegas asignadas). Incluye franjas por **muelle/equipo de descarga**, notificaciones in-app y por correo, recordatorios automáticos y tareas en segundo plano (no presentada, purga de notificaciones y proveedores suspendidos).

| Entorno | URL |
|---------|-----|
| Frontend (producción) | https://frontend-ferragro.vercel.app |
| API (producción) | https://ferragro-api.onrender.com |
| Health / versión API | https://ferragro-api.onrender.com/health |
| Swagger (producción) | https://ferragro-api.onrender.com/docs |
| Repositorio | https://github.com/einitbarajas/citas-ferragro |

Guía operativa detallada (SMTP, credenciales admin, diagnóstico): [`docs/GUIA_OPERACION_PRODUCCION.docx`](docs/GUIA_OPERACION_PRODUCCION.docx). Checklist rápido Render: [`PASOS-ENTRAR-PORTAL.md`](PASOS-ENTRAR-PORTAL.md). Índice de documentación: [`docs/README.txt`](docs/README.txt).

**CI:** en cada push/PR a `main` se ejecutan pruebas del API (sin BD y con PostgreSQL), `npm run build` del frontend (ver [`.github/workflows/ci.yml`](.github/workflows/ci.yml)). Preparar BD local para pytest: `db/ci-prepare-database.sh` (requiere `psql` y variables `PG*`).

## 1) Estructura del proyecto

```txt
.
├── backend
│   ├── requirements.txt
│   └── app
│       ├── main.py
│       ├── api
│       │   ├── auth.py
│       │   ├── appointments.py
│       │   ├── crud.py
│       │   └── admin.py
│       ├── core
│       │   ├── config.py
│       │   └── security.py
│       ├── db
│       │   ├── base.py
│       │   └── session.py
│       ├── models
│       │   ├── user.py
│       │   ├── appointment.py
│       │   └── audit_log.py
│       ├── schemas
│       │   ├── auth.py
│       │   ├── user.py
│       │   ├── appointment.py
│       │   └── audit.py
│       └── services
│           ├── appointment_service.py
│           ├── appointment_extension.py
│           ├── notification_service.py
│           ├── email_dispatch.py / mailer.py / email_utils.py
│           ├── reminder_scheduler.py
│           ├── no_presentada_scheduler.py
│           ├── notification_purge_scheduler.py
│           └── warehouse_scope.py
├── db
│   ├── README.md
│   ├── PsqlDb.ps1
│   ├── run-database-all.ps1
│   ├── run-database-crud.ps1
│   ├── ci-prepare-database.sh
│   ├── init
│   │   ├── 001_schema.sql … 023_admin_bodega_usuario.sql
│   ├── seeds
│   │   └── 003_seed_data.sql
│   └── database-crud
└── frontend
    ├── package.json
    ├── vite.config.js
    └── src
        ├── api/client.js
        ├── context/AuthContext.jsx
        ├── components
        │   ├── AppointmentForm.jsx / AppointmentList.jsx
        │   ├── NotificationCenter.jsx
        │   ├── ProviderAppointmentNotificationModal.jsx
        │   └── StaffRangeFilterGrid.jsx, MonthYearSelects.jsx, …
        ├── pages
        │   ├── LoginPage.jsx / DashboardPage.jsx / LandingPage.jsx
        └── utils
            ├── appointmentSlots.js / businessTime.js / reportRange.js
            └── providerAvailability.js
```

## 2) Modelos de base de datos (PostgreSQL)

Tablas principales (nombres en español en BD; el backend mapea a modelos Python):

- **`Credenciales`**: correo y hash de contraseña (login unificado).
- **`Usuarios`**: personal interno; roles en `Rol`: `Admin`, `Logistica`, **`AdminBodega`**; PK `IdDocumento`; enlazan `IdCredencial`.
- **`UsuariosBodegas`**: bodegas asignadas a un usuario `AdminBodega` (migración `020_admin_bodega.sql`).
- **`Bodegas`** / equipos de descarga: franjas y citas por muelle (`016`–`019` en `db/init/`).
- **`Proveedores`**: empresa; PK `IdNit`; correo de contacto y `IdCredencial`; el JWT de proveedor usa `sub` = NIT.
- **`Citas`**: cita de entrega (material, ventana horaria, estado, bodega y equipo).
- **`Notificaciones`**: avisos in-app por rol/proveedor (creada por el API; purga según `NOTIFICATION_RETENTION_DAYS`).
- **`HistorialCambios`**: auditoría (actor = documento interno o NIT en texto, sin FK estricta a usuarios).

Detalle y scripts: carpeta `db/` y `db/README.md`. Orquestación en Windows: `db\run-database-all.ps1` (aplica `001`–`023` + funciones CRUD). Tras clonar o actualizar una BD existente, revisa migraciones pendientes en `db/init/` (p. ej. `016`–`023` para equipos de descarga, integridad y Admin de bodega).

## 3) Endpoints backend

### Auth
- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`

### Citas y operación (`/api/crud/...` — contrato principal del frontend)
- Citas, bodegas, franjas, usuarios, proveedores, historial, etc.
- Roles de staff: **Admin**, **Logistica**, **AdminBodega** (este último filtrado por bodegas asignadas).

### Citas legacy (`/api/appointments` si el router está montado en `main.py`)
- `POST` (rol **Proveedor**): validación de anticipación y conflicto horario
- `GET` con `mode=list|day|month`
- `PATCH .../status` y `PATCH .../extend` (**Admin** / **Logistica**)

### Notificaciones (`/api/v1/notifications` — todos los roles autenticados)
- `GET /` — listado (filtro `unread_only`, paginación)
- `PATCH /{id}/read` y `PATCH /read-all`
- `DELETE /all`

### Administración
- `GET /api/admin/logs` (solo admin)

### Tareas en segundo plano (arranque del API)

Con el servidor en marcha se ejecutan bucles asyncio (ver `backend/app/main.py`):

| Scheduler | Función |
|-----------|---------|
| `reminder_scheduler` | Recordatorios de citas próximas (correo + in-app) |
| `no_presentada_scheduler` | Marca **no presentada** si la cita sigue en `revisado` tras el inicio + gracia (`APPOINTMENT_FINALIZATION_GRACE_MINUTES`, default 15) |
| `notification_purge_scheduler` | Elimina notificaciones más antiguas que `NOTIFICATION_RETENTION_DAYS` |
| `provider_purge_scheduler` | Purga proveedores suspendidos tras `PROVIDER_PURGE_AFTER_DAYS` |

## 3.1) Contrato API sincronizado Frontend/Backend

- Base URL API: `VITE_API_URL` (frontend) debe apuntar al host/puerto del backend (por defecto `http://localhost:8000`).
- Autenticación: `Authorization: Bearer <token>` en todas las rutas protegidas.
- Formato de respuesta estándar:
  - `{ "success": true|false, "data": <obj|array|null>, "message": "<texto>" }`
- Documentación interactiva:
  - Swagger UI: `http://localhost:8000/docs`
  - OpenAPI JSON: `http://localhost:8000/openapi.json`

### Endpoints activos usados por frontend

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET|POST|PUT /api/crud/appointments` (y rutas de bodegas, franjas, usuarios según rol)
- `GET /api/crud/change-logs`
- `GET|PATCH|DELETE /api/v1/notifications` (centro de notificaciones en el panel)

### Flujo de autenticación (Access + Refresh Token)

- Al iniciar sesión (`POST /api/auth/login`), el backend entrega:
  - `access_token` en el body (JWT de corta duración).
  - `refresh_token` en cookie `HttpOnly` (no accesible desde JavaScript).
- El frontend guarda solo el `access_token` en `localStorage` y lo envía en `Authorization: Bearer <token>`.
- Cuando el `access_token` expira, el frontend llama `POST /api/auth/refresh` con `withCredentials=true`:
  - si el `refresh_token` es válido, recibe un nuevo `access_token`;
  - además, el backend rota/renueva la cookie de refresh.
- Al cerrar sesión (`POST /api/auth/logout`), el backend elimina la cookie de refresh y el frontend limpia sesión local.

> Nota de seguridad: en producción debes usar HTTPS y configurar `refresh_cookie_secure=true` para que el navegador solo envíe la cookie por conexión segura.

## 4) Componentes principales frontend

- `LoginPage` / `LandingPage`: acceso y página pública
- `DashboardPage`: tablero por rol (`Admin`, `Logistica`, **`AdminBodega`**, `Proveedor`)
- `AppointmentForm`: agendar cita (proveedor; bodega → muelle → franja horaria)
- `AppointmentList`, `AppointmentReschedulePanel`, `StaffAppointmentChangeConfirm`: operación de citas
- `NotificationCenter`: campana de notificaciones (polling al API)
- `ProviderAppointmentNotificationModal`: aviso al proveedor tras cambios de cita por staff
- `StaffRangeFilterGrid` / `MonthYearSelects`: filtros de informes y calendario por rango
- Utilidades `appointmentSlots.js`, `businessTime.js`, `reportRange.js`: franjas, zona horaria de negocio y rangos de reporte
- **AdminBodega**: mismo panel operativo que logística, limitado a `UsuariosBodegas` (sin administración global de usuarios/roles)
- Panel de auditoría y configuraciones para `Admin`

## 5) Flujo completo de ejemplo

1. Proveedor inicia sesión y crea cita (`POST /api/crud/appointments` o legacy `POST /api/appointments`) eligiendo bodega, muelle y franja.
2. El sistema valida anticipación mínima (`APPOINTMENT_MINIMUM_NOTICE_HOURS`, default 24 h), franja en `BUSINESS_TIMEZONE` y ausencia de conflicto en el mismo muelle.
3. Staff (`Logistica` / `AdminBodega` / `Admin`) ve la cita; el proveedor recibe notificación in-app y correo si SMTP está configurado.
4. Logística marca la cita como `revisado`; si el proveedor no asiste, tras la gracia configurada el scheduler puede pasarla a `no presentada`.
5. Si aplica, se extiende la duración (`PATCH .../extend`) solo sin solapamiento con la siguiente cita del mismo equipo.
6. Admin revisa `GET /api/admin/logs` y el historial CRUD de cambios.

## Puesta en marcha

Orden recomendado: configurar `.env` (backend y frontend) → backend → frontend. Para desarrollo habitual abre **dos terminales**: una para el backend y otra para el frontend.

### Requisitos previos

- **Python** 3.x (con `pip`)
- **Node.js** y **npm**
- **PostgreSQL** 12+ instalado

### Paso 1: PostgreSQL local y `.env`

Con **PostgreSQL** instalado en local, el servidor suele escuchar en el puerto **5432**.

1. Crea la base si aún no existe (desde **pgAdmin** o `psql`): `CREATE DATABASE db_trabajo;`
2. Copia `.env.example` a `.env` en la **raíz del proyecto** y define al menos:
   - `DATABASE_URL` con tu contraseña de `postgres`
   - `SECRET_KEY` (valor largo y aleatorio)
   - JWT/cookies: `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `REFRESH_COOKIE_*` (`REFRESH_COOKIE_SECURE=false` en local HTTP)
   - `BUSINESS_TIMEZONE=America/Bogota` (validación de franjas)
   - Opcional local: `SMTP_PROFILE=office365` (o `gmail`) + `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM_EMAIL` para correos reales (ver `.env.example`)
   - Opcional: `APPOINTMENT_CANCEL_MINIMUM_NOTICE_HOURS` (default `12`), `NOTIFICATION_RETENTION_DAYS` (default `30`)
3. Desde PowerShell en la carpeta **`db`**, aplica esquema, parche de historial, funciones CRUD y (opcional) seed:

   ```powershell
   cd db
   .\run-database-all.ps1          # sin datos demo
   .\run-database-all.ps1 -Seed    # trunca y carga 003_seed_data.sql (solo dev)
   ```

   Equivale a ejecutar `init/001`–`023` y `run-database-crud.ps1` en orden. Más detalle en `db/README.md`.

> Nota: al arrancar el backend, `create_all` puede crear tablas faltantes según modelos SQLAlchemy; la fuente de verdad para tipos ENUM, triggers y funciones PL/pgSQL sigue siendo la carpeta `db/`.

### Paso 2: Backend (entorno virtual)

Trabaja siempre **desde la carpeta `backend`**. El punto de entrada es `main.py` en esa carpeta (levanta Uvicorn en el puerto **8000**).

**Primera vez — crear el entorno virtual e instalar dependencias**

1. `cd backend`
2. Crear el venv (el nombre `.venv` es el habitual en este proyecto):

   ```bash
   py -m venv .venv
   ```

3. **Activar** el entorno virtual (el prompt suele mostrar `(.venv)`):

   - **Windows (PowerShell):**

     ```powershell
     .\.venv\Scripts\Activate.ps1
     ```

     Si aparece un error de política de ejecución, en PowerShell como usuario actual puedes permitir scripts locales con:

     ```powershell
     Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
     ```

   - **Windows (CMD):**

     ```cmd
     .venv\Scripts\activate.bat
     ```

   - **macOS / Linux:**

     ```bash
     source .venv/bin/activate
     ```

4. Instalar dependencias:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

   > Recomendado en Windows: usar `python -m pip` del venv evita errores del launcher de `pip.exe` cuando el proyecto se mueve de carpeta.

**Pruebas automatizadas**

Con `DATABASE_URL` válido en el `.env` de la raíz y esquema + CRUD aplicados (`db\run-database-all.ps1`):

```powershell
# Desde la raíz del repo (carpeta "trabajo ferragro")
cd backend
$env:PYTHONPATH="."
.\.venv\Scripts\python.exe -m pytest tests/ -v
.\.venv\Scripts\python.exe scripts\system_check.py
# operational_check: arranca el API en OTRA terminal (py main.py) y luego:
.\.venv\Scripts\python.exe scripts\operational_check.py

cd ..\frontend   # solo si sigues en backend\; si estás en la raíz, usa: cd frontend
npm run lint:a11y
npm run build
```

Si ya estás en la **raíz** del repo y no en `backend\`, el front se prueba así:

```powershell
cd frontend
npm run lint:a11y
npm run build
```

Si ya activaste el venv (`.\.venv\Scripts\Activate.ps1`), puedes usar `python -m pytest ...`.

En **Windows**, si `python` no existe en el PATH (mensaje de Microsoft Store), usa siempre la ruta del venv como arriba, o el launcher: `py -3 -m pytest ...` (con Python instalado desde [python.org](https://www.python.org/downloads/)).

Las pruebas de BD usan transacciones que se revierten al terminar (no dejan datos de prueba). Suite actual: **85 tests** en `backend/tests/` (detalle en [`docs/PRUEBAS.docx`](docs/PRUEBAS.docx)).

**Equipos de descarga por bodega:** migraciones `016`–`022` en `db/init/` (incluidas en `run-database-all.ps1`). Tras cambiar SQL en `database-crud/`, ejecutar `db\run-database-crud.ps1`. En **Admin → Bodegas**, usa **Nombres de muelles** para etiquetar cada equipo.

**Administrador de bodega (`AdminBodega`):** migraciones `020`–`023` (`020_admin_bodega.sql`, integridad `021`, usuario opcional `023`). En BD ya desplegada, aplica solo los `.sql` que falten con `psql` o vuelve a ejecutar `run-database-all.ps1` (los scripts son idempotentes donde aplica).

**Comprobación operativa al 100%** (esquema BD + API en marcha):

```powershell
cd backend
$env:PYTHONPATH="."
.\.venv\Scripts\python.exe scripts\operational_check.py
# Opcional: flujos autenticados (admin/logística)
$env:OPERATIONAL_LOGIN_EMAIL="tu@correo.com"
$env:OPERATIONAL_LOGIN_PASSWORD="tu-contraseña"
.\.venv\Scripts\python.exe scripts\operational_check.py
```

Debe imprimir `Resultado: operativo al 100%`. Checklist manual en UI: admin franjas por muelle, proveedor bodega → calendario → muelle → horario, dos citas misma hora en equipos distintos.

**Cada vez que vuelvas a desarrollar**

1. `cd backend`
2. Activa el venv con el comando de tu sistema (PowerShell / CMD / bash, como arriba).
3. Arranca el backend desde `main.py`:

   ```powershell
   .\.venv\Scripts\python.exe main.py
   ```

   (O `py main.py` / `python main.py` si el venv está activado y `python` apunta al intérprete correcto.)

4. Backend disponible en **`http://localhost:8000`** (Swagger: **`http://localhost:8000/docs`**).

Para salir del entorno virtual cuando termines: `deactivate`.

#### Solución rápida de errores comunes de venv/pip en Windows

Si aparece un error como `Fatal error in launcher` al ejecutar `pip`, normalmente el `pip.exe` quedó apuntando a una ruta antigua del proyecto.

Ejecuta estos comandos dentro de `backend`:

```powershell
.\.venv\Scripts\python.exe -m ensurepip --upgrade
.\.venv\Scripts\python.exe -m pip install --upgrade --force-reinstall pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

##### `ImportError: DLL load failed ... _pydantic_core` o `pip.exe: Acceso denegado` (Windows)

Suele ser **antivirus / Microsoft Defender** bloqueando ejecutables y extensiones `.pyd` dentro de la carpeta del proyecto (por ejemplo `C:\dev\...`). No es un fallo del código del backend.

**Opción recomendada (venv fuera del repo):** desde PowerShell en la raíz del repo o en `backend`:

```powershell
cd backend
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force
.\setup-external-venv.ps1
```

Ese script crea un entorno en `%USERPROFILE%\.venvs\ferragro-backend-py312`, instala `requirements.txt` y deja la ruta en `backend\.venv_external`. Luego activa ese venv y arranca como siempre:

```powershell
& "$env:USERPROFILE\.venvs\ferragro-backend-py312\Scripts\Activate.ps1"
py .\main.py
```

O, sin activar manualmente el venv (usa `backend\.venv_external` si existe):

```powershell
cd backend
.\run-backend.ps1
```

`main.py` arranca Uvicorn **sin hot-reload por defecto** (`reload=False`). Con `reload=True`, el proceso hijo del reloader en Windows a veces vuelve a fallar al cargar `_pydantic_core` (“Acceso denegado”) aunque el venv esté bien. Si necesitas recarga automática y tu equipo no bloquea DLLs en subprocesos:

```powershell
$env:UVICORN_RELOAD = "1"
.\run-backend.ps1
```

**Si `run-backend.ps1` sigue fallando con `_pydantic_core` / “Acceso denegado”** (incluso con venv externo), el sistema está bloqueando la DLL en **cualquier** Python del escritorio. Tienes dos salidas:

###### A) Exclusión en Microsoft Defender (recomendado en Windows nativo)

1. Abre **Seguridad de Windows** → **Protección contra virus y amenazas**.
2. **Administrar configuración** → baja a **Exclusiones** → **Agregar o quitar exclusiones**.
3. **Agregar una exclusión** → **Carpeta** y añade **las dos** (si tu política lo permite), sustituyendo tu usuario si hace falta:

   - `%USERPROFILE%\.venvs\ferragro-backend-py312` (por ejemplo `C:\Users\TU_USUARIO\.venvs\ferragro-backend-py312`)
   - La carpeta `backend` del repo (por ejemplo `C:\dev\trabajo ferragro\backend`)

4. Cierra y vuelve a abrir PowerShell y ejecuta `.\run-backend.ps1`.

###### B) No puedes tocar Defender (sin permisos de administrador / política corporativa)

La opción A no está disponible si el botón de exclusiones no aparece o está deshabilitado. En ese caso el antivirus lo controla **tu empresa** o una política global. Puedes:

1. **Pedir a soporte / TI** que añadan exclusiones (o que desbloqueen Python) para estas rutas, copiando el texto tal cual en el ticket:

   - Carpeta del venv: `C:\Users\ebarajas\.venvs\ferragro-backend-py312` (ajusta el usuario si hace falta).
   - Carpeta del proyecto: `C:\dev\trabajo ferragro\backend`.
   - Motivo: *ImportError al cargar `pydantic_core` (`_pydantic_core*.pyd`): Acceso denegado; bloqueo de extensiones nativas de Python.*

2. **WSL2 (Ubuntu)** — muchas veces se puede instalar desde Microsoft Store **sin** ser admin de Defender: el backend corre en Linux y usa `.so`, no la DLL bloqueada en Windows.

   En **PowerShell** (una vez, puede pedir reinicio):

   ```powershell
   wsl --install -d Ubuntu
   ```

   Cuando Ubuntu abra, dentro de WSL:

   ```bash
   sudo apt update && sudo apt install -y python3-venv python3-pip
   cd "/mnt/c/dev/trabajo ferragro/backend"
   python3 -m venv .venv-wsl
   source .venv-wsl/bin/activate
   pip install -r requirements.txt
   python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

   Comprueba con `python3 --version` que sea **3.11 o superior** (idealmente 3.12). El navegador en Windows suele poder usar **`http://localhost:8000`** contra ese servidor en WSL. El frontend en Windows (`npm run dev`) puede seguir con `VITE_API_URL=http://localhost:8000`.

### Paso 3: Configurar `.env` del frontend

En `frontend/.env` (o copia `frontend/.env.example`) define la URL del backend para Vite:

```env
VITE_API_URL=http://localhost:8000
VITE_API_PREFIX=/api/v1
# Opcional (deben coincidir con el backend si los cambias):
# VITE_NOTIFICATION_RETENTION_DAYS=30
# VITE_APPOINTMENT_CANCEL_MINIMUM_NOTICE_HOURS=12
# VITE_API_TIMEOUT_MS=45000
```

### Paso 4: Frontend

En **otra terminal** (el backend puede seguir corriendo):

1. Ve a la carpeta del cliente:

   ```bash
   cd frontend
   ```

2. Instala dependencias (solo la primera vez o tras cambios en `package.json`):

   ```bash
   npm install
   ```

3. Arranca el servidor de desarrollo de Vite:

   ```bash
   npm run dev
   ```

4. Frontend en **`http://localhost:2711`**.

Si el API no responde, comprueba que `VITE_API_URL` apunte al backend (por defecto suele ser `http://localhost:8000`; ver sección **3.1) Contrato API**).

#### Nota de seguridad (headers/CSP y escaneo)

El frontend y backend incluyen cabeceras de seguridad (`Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`, etc.).

Para validar cambios con ZAP o herramientas similares:

1. Reinicia backend y frontend después de editar configuración de seguridad.
2. Limpia historial/caché del escáner antes de volver a ejecutar.
3. En modo desarrollo (`npm run dev`) pueden aparecer alertas informativas por tooling de frontend; para validar un escenario más cercano a producción usa `npm run build` y `npm run preview` (o el servidor estático que despliegues).

Documentación operativa (RPO/RTO, backups, roles DB): `docs/operacion_continuidad.docx`. Índice completo: `docs/README.txt`.

## 6) Despliegue en la nube (Vercel + Render)

La documentación funcional permanece en este repo (`README.md`, `docs/`, `db/README.md`). Producción Ferragro:

| Servicio | Nombre | URL / panel |
|----------|--------|-------------|
| Frontend | `frontend` (Vercel) | https://frontend-ferragro.vercel.app |
| API | `ferragro-api` (Render) | https://ferragro-api.onrender.com |
| PostgreSQL | `ferragro-db` (Render) | Panel BD en [Render](https://dashboard.render.com/) |

### 6.1) Render (PostgreSQL + backend)

1. En [Render](https://render.com), conecta el repositorio `einitbarajas/citas-ferragro` (rama `main`).
2. Crea un **Blueprint** desde `render.yaml` (recomendado) o servicios manuales:
   - **PostgreSQL** (`ferragro-db`).
   - **Web Service** Python (`ferragro-api`) con **Root Directory** `backend`.
   - **Build:** `pip install -r requirements.txt`
   - **Start:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Health check:** `/health`
3. Variables en `ferragro-api` (ver `.env.example` y [`docs/GUIA_OPERACION_PRODUCCION.docx`](docs/GUIA_OPERACION_PRODUCCION.docx)):
   - Obligatorias: `ENVIRONMENT=production`, `DATABASE_URL`, `SECRET_KEY`, `CORS_ORIGINS`, cookies refresh en HTTPS (`REFRESH_COOKIE_SECURE=true`, `REFRESH_COOKIE_SAMESITE=none`).
   - **SMTP** (un solo servidor para todo el portal): `SMTP_PROFILE=office365` o `SMTP_HOST` + `SMTP_USER` + `SMTP_PASSWORD` + `SMTP_FROM_EMAIL`. Sin SMTP no hay bienvenida, recuperación de contraseña ni avisos de citas (solo logs).
   - Recomendadas: `BUSINESS_TIMEZONE=America/Bogota`, `NOTIFICATION_RETENTION_DAYS`, `APPOINTMENT_CANCEL_MINIMUM_NOTICE_HOURS`.
4. Con la BD **Available**, aplica esquema y CRUD desde tu PC con la **External Database URL**:

   ```powershell
   cd db
   $env:DATABASE_URL = "postgresql://..."   # External URL de ferragro-db
   .\run-database-all.ps1                   # sin -Seed en producción
   .\run-database-crud.ps1
   ```

   Migraciones nuevas en bases ya existentes: aplica los `.sql` pendientes en `db/init/` (desde `016` en adelante si la BD es antigua) o ejecuta de nuevo `.\run-database-all.ps1` contra la External URL.

5. Comprueba versión desplegada:

   ```text
   GET https://ferragro-api.onrender.com/health
   → "build_id": "2026-05-28-deploy-main-v1"   (valor actual en backend/app/main.py → API_BUILD_ID)
   ```

   Si el `build_id` no coincide con el de `main.py`, el servicio **no** tiene el último código aunque GitHub sí. Checklist: [`PASOS-ENTRAR-PORTAL.md`](PASOS-ENTRAR-PORTAL.md).

#### Render no se actualiza solo (muy frecuente)

Subir a GitHub **no** cambia el API si en **Events** el último deploy es de hace días (commit viejo, p. ej. `10fe606`):

1. Panel: https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0  
2. **Manual Deploy** → **Deploy latest commit** (no Rollback).  
3. **Settings → Build & Deploy:** repo `citas-ferragro`, rama `main`, **Root Directory** `backend`, **Auto-Deploy** On.  
4. **Deploy Hook** obligatorio para CI: secreto `RENDER_DEPLOY_HOOK` en GitHub (workflow `deploy-render-api.yml` falla si falta).
5. Guía completa enlace Git: [`docs/CONECTAR_GIT_VERCEL_RENDER.docx`](docs/CONECTAR_GIT_VERCEL_RENDER.docx).

Scripts en el repo:

```powershell
.\scripts\conectar-git-produccion.ps1      # paneles + checklist
.\scripts\setup-github-deploy-secrets.ps1 # VERCEL_TOKEN y RENDER_DEPLOY_HOOK
```

```powershell
.\scripts\deploy-render-ahora.ps1      # requiere $env:RENDER_DEPLOY_HOOK o abre el panel
.\scripts\deploy-produccion.ps1        # push + hook + espera /health
cd frontend; npx vercel deploy --prod --yes   # front sin depender del auto-deploy de Vercel
```

### 6.2) Vercel (frontend)

1. Proyecto `frontend` en equipo `ferragro`; **Root Directory:** `frontend` (al conectar Git).
2. **Conectar GitHub:** [Settings → Git](https://vercel.com/ferragro/frontend/settings/git) → repo `einitbarajas/citas-ferragro`, rama `main`. Si el panel no deja conectar, usa el workflow Actions con secreto `VERCEL_TOKEN` (ver [`docs/CONECTAR_GIT_VERCEL_RENDER.docx`](docs/CONECTAR_GIT_VERCEL_RENDER.docx)).
3. Variables **Production**:
   - `VITE_API_URL=https://ferragro-api.onrender.com` (sin `/` final)
   - `VITE_API_PREFIX=/api/v1`
4. Tras `git push` a `main` (cambios en `frontend/`), debe desplegar solo (Git o workflow `deploy-vercel-frontend.yml`).

### 6.3) Enlazar front y back

1. En Render, `CORS_ORIGINS=https://frontend-ferragro.vercel.app` (y otros dominios si aplica).
2. Redespliega el API tras cambiar CORS.
3. Redespliega Vercel si cambiaste `VITE_API_URL`.
4. Prueba login, refresh, logout y panel (recarga forzada Ctrl+F5 si el navegador cachea el JS).

### 6.4) Notas

- Plan Free de Render: el API puede **dormir** (~15 min sin tráfico); la primera petición tarda 30–90 s.
- Front (Vercel) y BD suelen responder al instante; lo lento suele ser el cold start del API.
- Cookie refresh en producción: `Secure` + `SameSite=None` (dominios distintos Vercel/Render).
- Fuente de verdad del esquema: `db/init/` + `database-crud/`; `create_all` al arrancar no sustituye triggers ni funciones PL/pgSQL.
- Checklist portal y admin producción: [`PASOS-ENTRAR-PORTAL.md`](PASOS-ENTRAR-PORTAL.md).
