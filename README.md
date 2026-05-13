# Ferragro - Gestión de Citas de Entrega

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
│           └── appointment_service.py
├── db
│   ├── README.md
│   ├── PsqlDb.ps1
│   ├── run-database-all.ps1
│   ├── run-database-crud.ps1
│   ├── init
│   │   ├── 001_schema.sql
│   │   ├── 002_audit_triggers.sql
│   │   └── 003_historial_id_actor_drop_fk.sql
│   ├── seeds
│   │   └── 003_seed_data.sql
│   └── database-crud
└── frontend
    ├── package.json
    ├── vite.config.js
    ├── tailwind.config.js
    ├── postcss.config.js
    └── src
        ├── main.jsx
        ├── App.jsx
        ├── api/client.js
        ├── context/AuthContext.jsx
        ├── components
        │   ├── AppointmentForm.jsx
        │   └── AppointmentList.jsx
        └── pages
            ├── LoginPage.jsx
            └── DashboardPage.jsx
```

## 2) Modelos de base de datos (PostgreSQL)

Tablas principales (nombres en español en BD; el backend mapea a modelos Python):

- **`Credenciales`**: correo y hash de contraseña (login unificado).
- **`Usuarios`**: personal interno (`Admin`, `Logistica` en `Rol`); PK `IdDocumento`; enlazan `IdCredencial`.
- **`Proveedores`**: empresa; PK `IdNit`; correo de contacto y `IdCredencial`; el JWT de proveedor usa `sub` = NIT.
- **`Citas`**: cita de entrega (material, ventana horaria, estado).
- **`HistorialCambios`**: auditoría (actor = documento interno o NIT en texto, sin FK estricta a usuarios).

Detalle y scripts: carpeta `db/` y `db/README.md`. Orquestación en Windows: `db\run-database-all.ps1`.

## 3) Endpoints backend

### Auth
- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`

### Citas (`/api/appointments` si el router está montado en `main.py`)
- `POST` (rol **Proveedor**): validación de anticipación y conflicto horario
- `GET` con `mode=list|day|month`
- `PATCH .../status` y `PATCH .../extend` (**Admin** / **Logistica**)

### Administración
- `GET /api/admin/logs` (solo admin)

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
- `GET /api/crud/appointments`
- `POST /api/crud/appointments`
- `PUT /api/crud/appointments/{appointment_id}`
- `GET /api/crud/change-logs`

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

- `LoginPage`: registro/inicio de sesión
- `DashboardPage`: tablero por rol
- `AppointmentForm`: agendar cita (proveedor)
- `AppointmentList`: visualizar y gestionar citas (Admin / Logistica)
- Panel de auditoría para `admin` con logs de cambios

## 5) Flujo completo de ejemplo

1. Proveedor inicia sesión y crea cita (`POST /api/appointments`) con descripción como "1 tonelada de cemento".
2. El sistema valida:
   - anticipación mínima de 24 horas
   - no conflicto de horarios
3. Personal de logística ve la cita y cambia estado a `revisado`.
4. Si aplica, se extiende la duración solo si no hay solapamiento con la siguiente cita.
5. Admin revisa en `GET /api/admin/logs` quién cambió estado/duración y cuándo.

## Puesta en marcha

Orden recomendado: configurar `.env` (backend y frontend) → backend → frontend. Para desarrollo habitual abre **dos terminales**: una para el backend y otra para el frontend.

### Requisitos previos

- **Python** 3.x (con `pip`)
- **Node.js** y **npm**
- **PostgreSQL** 12+ instalado

### Paso 1: PostgreSQL local y `.env`

Con **PostgreSQL** instalado en local, el servidor suele escuchar en el puerto **5432**.

1. Crea la base si aún no existe (desde **pgAdmin** o `psql`): `CREATE DATABASE db_trabajo;`
2. En el `.env` en la **raíz del proyecto** define `DATABASE_URL` con tu contraseña de `postgres`.
   Además, para autenticación JWT/cookies configura:
   - `SECRET_KEY` con un valor largo y aleatorio
   - `ALGORITHM=HS256` (o el algoritmo que definas en backend)
   - `ACCESS_TOKEN_EXPIRE_MINUTES` (ejemplo: `120`)
   - `REFRESH_TOKEN_EXPIRE_DAYS` (ejemplo: `7`)
   - `REFRESH_COOKIE_NAME` (ejemplo: `refresh_token`)
   - `REFRESH_COOKIE_SECURE` (`false` en local HTTP, `true` en producción HTTPS)
   - `REFRESH_COOKIE_SAMESITE` (`lax` o `strict` según tu escenario)
3. Desde PowerShell en la carpeta **`db`**, aplica esquema, parche de historial, funciones CRUD y (opcional) seed:

   ```powershell
   cd db
   .\run-database-all.ps1          # sin datos demo
   .\run-database-all.ps1 -Seed    # trunca y carga 003_seed_data.sql (solo dev)
   ```

   Equivale a ejecutar `001_schema.sql`, `002_audit_triggers.sql`, `003_historial_id_actor_drop_fk.sql` y `run-database-crud.ps1` en orden. Más detalle en `db/README.md`.

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

**Pruebas (funciones CRUD PL/pgSQL en PostgreSQL)**

Con `DATABASE_URL` válido en el `.env` de la raíz del repo y el esquema + CRUD aplicados (`db\run-database-all.ps1`):

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_db_crud_functions.py -v
```

Si ya activaste el venv (`.\.venv\Scripts\Activate.ps1`), puedes usar `python -m pytest ...`.

En **Windows**, si `python` no existe en el PATH (mensaje de Microsoft Store), usa siempre la ruta del venv como arriba, o el launcher: `py -3 -m pytest ...` (con Python instalado desde [python.org](https://www.python.org/downloads/)).

Cada prueba usa una transacción que se revierte al terminar (no deja datos de prueba en la base).

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

En `frontend/.env` define la URL del backend para Vite:

```env
VITE_API_URL=http://localhost:8000
# Prefijo versionado usado por el frontend (el backend expone /api y /api/v1)
VITE_API_PREFIX=/api/v1
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

Documentación operativa (RPO/RTO, backups, roles DB): `documentacion/operacion_continuidad.md`.

## 5) Despliegue en la nube (Vercel + Render)

La documentación funcional y técnica permanece en este repositorio de GitHub (`README.md`, `documentacion/`, `db/README.md`). El contrato del API en producción se consulta en `https://<tu-api>.onrender.com/docs`.

### 5.1) Render (PostgreSQL + backend)

1. En [Render](https://render.com), conecta el repositorio de GitHub.
2. Crea un **Blueprint** desde `render.yaml` (recomendado) o crea manualmente:
   - **PostgreSQL** (plan Free o superior).
   - **Web Service** Python con **Root Directory** `backend`.
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Health check path:** `/health`
3. Variables de entorno del servicio (además de `DATABASE_URL` enlazada a la BD):
   - `ENVIRONMENT=production`
   - `SECRET_KEY` (valor largo y aleatorio; Render puede generarlo en el Blueprint)
   - `CORS_ORIGINS` (se completa en el paso 5.3)
   - Opcional: SMTP y Cloudinary (mismas claves que en `.env.example`)
4. Cuando la BD esté **Available**, aplica el esquema desde tu máquina con la **External Database URL** de Render:

   ```bash
   export DATABASE_URL="postgresql://..."
   bash db/run-database-all.sh
   ```

   No uses `--seed` en producción salvo que quieras datos de demostración.

5. Comprueba `https://<tu-api>.onrender.com/health` y `/docs`.

### 5.2) Vercel (frontend)

1. En [Vercel](https://vercel.com), importa el mismo repositorio de GitHub.
2. **Root Directory:** `frontend`
3. **Framework Preset:** Vite (o deja que detecte `vercel.json`).
4. Variables de entorno de **Production** (y Preview si quieres):
   - `VITE_API_URL=https://<tu-api>.onrender.com` (sin barra final)
   - `VITE_API_PREFIX=/api/v1`
5. Despliega y anota la URL HTTPS del sitio (por ejemplo `https://tu-proyecto.vercel.app`).

### 5.3) Enlazar front y back

1. En Render, edita el Web Service y define `CORS_ORIGINS` con la URL HTTPS de Vercel (varias separadas por coma si tienes dominio custom y preview).
2. Redespliega el backend.
3. En Vercel, **Redeploy** el frontend si cambiaste `VITE_API_URL`.
4. Prueba login, refresh de sesión, logout y el panel con la URL de Vercel.

### 5.4) Notas

- El plan Free de Render puede **dormir** el API; la primera petición tras inactividad tarda más.
- Entre dominios distintos (Vercel + Render) la cookie de refresh usa `Secure` y `SameSite=None` en producción.
- Los scripts SQL viven en `db/`; el backend también ejecuta `create_all` al arrancar, pero el flujo recomendado es aplicar `db/run-database-all.sh` contra la BD de Render.
