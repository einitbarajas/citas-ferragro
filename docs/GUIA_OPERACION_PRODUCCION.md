# Guía de operación — Ferragro Citas (producción)

Documento de referencia para URLs, requisitos, arranque, diagnóstico y buenas prácticas del entorno desplegado (Vercel + Render + GitHub).

---

## 1. URLs del sistema

### Frontend (Vercel)

| Recurso | URL |
|---------|-----|
| Sitio web (producción) | https://frontend-ferragro.vercel.app |
| Panel Vercel | https://vercel.com/ferragro/frontend |

### Backend (Render — Web Service)

| Recurso | URL |
|---------|-----|
| API base | https://ferragro-api.onrender.com |
| Health check | https://ferragro-api.onrender.com/health |
| Documentación Swagger | https://ferragro-api.onrender.com/docs |
| Panel Render (servicio) | https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0 |

### Base de datos (Render — PostgreSQL)

PostgreSQL **no se abre en el navegador** como una web. Se administra desde el panel y se conecta con cliente SQL (psql, DBeaver, pgAdmin, scripts del repo).

| Recurso | Valor |
|---------|--------|
| Panel Render (BD) | https://dashboard.render.com/d/dpg-d82dfn4vikkc73a6mcj0-a |
| Nombre del servicio | `ferragro-db` |
| Host externo | `dpg-d82dfn4vikkc73a6mcj0-a.oregon-postgres.render.com` |
| Puerto | `5432` |
| Base de datos | `ferragro` |
| Usuario | `ferragro` |
| Región | Oregon (US West) |

La **URL de conexión completa** (`DATABASE_URL`) con contraseña está en Render → `ferragro-db` → **Connections** → **External Database URL**. No la publiques ni la subas a GitHub.

### Código y documentación (GitHub)

| Recurso | URL |
|---------|-----|
| Repositorio | https://github.com/einitbarajas/citas-ferragro |
| Rama de despliegue | `main` |

---

## 2. Qué se necesita para que funcione

### Servicios en la nube (siempre activos en la nube)

1. **Vercel** — sirve el frontend estático (build de Vite).
2. **Render** — ejecuta el API FastAPI (`ferragro-api`).
3. **Render PostgreSQL** — almacena datos (`ferragro-db`).
4. **GitHub** — código fuente; Render hace deploy automático al hacer push a `main`.

### Variables de entorno — Backend (Render → `ferragro-api`)

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `ENVIRONMENT` | Sí | `production` |
| `DATABASE_URL` | Sí | Conexión a `ferragro-db` |
| `SECRET_KEY` | Sí | Secreto largo para JWT (no compartir) |
| `CORS_ORIGINS` | Sí | `https://frontend-ferragro.vercel.app` (y otros dominios si los agregas) |
| `REFRESH_COOKIE_SECURE` | Sí | `true` |
| `REFRESH_COOKIE_SAMESITE` | Sí | `none` (front y back en dominios distintos) |
| `PYTHON_VERSION` | Recomendada | `3.12.8` |
| `SMTP_*` | No | Correo (recuperación de contraseña, avisos) |
| `CLOUDINARY_*` | No | Fotos de perfil |
| `BUSINESS_TIMEZONE` | No | Por defecto `America/Bogota` |

### Variables de entorno — Frontend (Vercel → proyecto `frontend`)

| Variable | Obligatoria | Valor en producción |
|----------|-------------|---------------------|
| `VITE_API_URL` | Sí | `https://ferragro-api.onrender.com` (sin `/` final) |
| `VITE_API_PREFIX` | Sí | `/api/v1` |

Tras cambiar variables en Vercel hay que hacer **Redeploy** del frontend.

### Base de datos

- Esquema y funciones SQL aplicados con `db/run-database-all.ps1` o `db/run-database-all.sh` contra la External Database URL.
- **No** ejecutar `-Seed` / `--seed` en producción (borra datos y carga demo).

### Cuentas y acceso

- Cuenta **Render** (workspace con `ferragro-db` y `ferragro-api`).
- Cuenta **Vercel** (equipo `ferragro`, proyecto `frontend`).
- Repositorio **público** en GitHub (Render plan Free necesita acceso al repo para deploy Git).

### Primer usuario Admin (obligatorio para operar el panel)

El rol **Admin** no se crea desde “Registrarme” en la web. Debe existir en la base de datos antes de poder crear usuarios de **Logística** u otros internos.

#### Credenciales del Admin inicial (producción Render)

| Campo | Valor |
|-------|--------|
| Correo | `admin@ferragro.com` |
| Contraseña | `FerragroAdmin2026!` |
| Documento | `90000001` |
| Nombre | Administrador Portal |
| Rol | Admin |

**Acceso:** https://frontend-ferragro.vercel.app → **Iniciar sesión** (no Registrarme).

> Cambia esta contraseña tras el primer acceso. Si la olvidas, vuelve a ejecutar `db/bootstrap-admin.ps1` con `-ResetPassword` (ver abajo).

#### Usuarios actualmente en la base de datos de producción

Consulta realizada contra `ferragro-db` en Render:

| Correo | Rol | Documento / NIT | Nombre |
|--------|-----|-----------------|--------|
| `admin@ferragro.com` | Admin | `90000001` | Administrador Portal |

**No hay** en este momento usuarios de Logística ni proveedores registrados en producción. Los creas así:

| Rol | Cómo se crea |
|-----|----------------|
| **Admin** | Solo con script `bootstrap-admin.ps1` o otro Admin en el panel |
| **Logística** | Panel Admin → **Crear usuario**, o registro público (pestaña Registrarme, rol Logística) |
| **Proveedor** | Registro público en la web (Registrarme) |

#### Usuarios de demostración (solo desarrollo local)

Si ejecutas `.\run-database-all.ps1 -Seed` en tu PC, se cargan datos de ejemplo (`db/seeds/003_seed_data.sql`). **No uses `-Seed` en producción** (borra tablas y pone hashes de prueba que no sirven para login real).

| Correo (demo) | Rol | Notas |
|---------------|-----|--------|
| `admin@ferragro.com` | Admin | Hash de ejemplo en seed — no válido para login |
| `logistica@ferragro.com` | Logística | Idem |
| `proveedor1@acero.com` | Proveedor | Empresa demo |
| `proveedor2@cemento.com` | Proveedor | Empresa demo |

En **producción** el único usuario real cargado con el script de bootstrap es el Admin de la tabla anterior.

#### Crear o restablecer el primer Admin en Render

Desde PowerShell, con la **External Database URL** de Render (`ferragro-db` → Connections):

```powershell
cd "c:\dev\trabajo ferragro\db"

# Crear Admin si no existe
.\bootstrap-admin.ps1 `
  -DatabaseUrl "postgresql://ferragro:PASSWORD@dpg-....oregon-postgres.render.com:5432/ferragro" `
  -Email "admin@ferragro.com" `
  -Password "TuClaveSegura12" `
  -DocumentId "90000001" `
  -FullName "Administrador Portal"

# Si el correo ya existe y solo quieres nueva contraseña
.\bootstrap-admin.ps1 -DatabaseUrl "postgresql://..." -Password "NuevaClave123" -ResetPassword
```

Requisito previo: esquema aplicado (`.\run-database-all.ps1` sin `-Seed` contra la misma BD).

#### Listar usuarios en la BD (consulta SQL)

```sql
-- Usuarios internos (Admin, Logística)
SELECT c."Correo", r."Nombre" AS rol, u."IdDocumento", u."NombreCompleto"
FROM "Usuarios" u
JOIN "Credenciales" c ON c."IdCredencial" = u."IdCredencial"
JOIN "Rol" r ON r."Id" = u."IdRol";

-- Proveedores
SELECT c."Correo", p."IdNit", p."NombreEmpresa"
FROM "Proveedores" p
JOIN "Credenciales" c ON c."IdCredencial" = p."IdCredencial";
```

---

## 3. Cómo “prender” el proyecto

### Producción (Vercel + Render)

**No hay un botón de encendido manual:** los servicios en la nube están desplegados de forma continua.

| Componente | Comportamiento |
|------------|----------------|
| Frontend (Vercel) | Siempre disponible en la URL de producción. |
| API (Render Free) | Puede **dormir** tras ~15 min sin tráfico. La **primera petición** tras dormir tarda 30–90 s (cold start). |
| Base de datos (Render Free) | Permanece activa; expira el plan gratuito de BD si no se renueva según políticas de Render (revisar avisos en el dashboard). |

**Para “despertar” el API:** abre en el navegador o ejecuta:

```text
https://ferragro-api.onrender.com/health
```

Cuando responda `{"success":true,...}`, el backend ya está listo. Luego entra al frontend y usa la aplicación con normalidad.

**Redespliegue manual (si hiciste cambios):**

- **Backend:** push a `main` en GitHub (auto-deploy) o en Render → `ferragro-api` → **Manual Deploy**.
- **Frontend:** en Vercel → **Deployments** → **Redeploy**, o desde la carpeta `frontend`:

  ```bash
  npx vercel deploy --prod
  ```

### Desarrollo local (en tu PC)

1. PostgreSQL local con base `db_trabajo` (o la que definas).
2. Archivo `.env` en la raíz del repo (copiar de `.env.example`).
3. Aplicar BD: `cd db` → `.\run-database-all.ps1` (opcional `-Seed` solo en dev).
4. Backend: `cd backend` → `python -m uvicorn app.main:app --reload --port 8000`
5. Frontend: `cd frontend` → `npm install` → `npm run dev` (puerto 2711, proxy al API).

Detalle completo en `README.md` secciones 3 y 4.

---

## 4. Cómo revisar si algo está fallando

### Checklist rápido (5 minutos)

1. **API vivo**

   ```text
   GET https://ferragro-api.onrender.com/health
   ```

   Respuesta esperada: HTTP 200 y `"status":"ok"`.

2. **Frontend carga**

   Abre https://frontend-ferragro.vercel.app — debe mostrar la landing/login, no pantalla de autenticación de Vercel.

3. **Login**

   Inicia sesión con el Admin (`admin@ferragro.com`) u otro usuario existente en la BD. Si falla:
   - Espera 1 minuto (cold start) y reintenta.
   - F12 → pestaña **Network**: las peticiones deben ir a `ferragro-api.onrender.com`, no a `localhost`.

4. **CORS**

   Si ves error de CORS en consola: en Render, `CORS_ORIGINS` debe incluir exactamente la URL del front (con `https://`, sin barra final).

### Dónde ver logs y estado

| Problema sospechado | Dónde mirar |
|---------------------|-------------|
| API caído o error 5xx | Render → `ferragro-api` → **Logs** |
| Build del API falló | Render → `ferragro-api` → **Events** / último deploy |
| BD no conecta | Render → `ferragro-db` → estado **Available**; revisar `DATABASE_URL` en el servicio API |
| Front no carga o build falló | Vercel → proyecto `frontend` → **Deployments** → logs de build |
| Variables mal en front | Vercel → **Settings** → **Environment Variables** |
| Cambios de código no llegan | GitHub: ¿push a `main`? Render/Vercel: ¿deploy exitoso? |

### Señales típicas de fallo

| Síntoma | Causa probable |
|---------|----------------|
| “No se pudo conectar con el API” | API dormido, URL incorrecta en `VITE_API_URL`, o API caído |
| Pantalla en blanco tras login | Error JS; revisar consola del navegador |
| 401 / sesión se pierde | Cookies bloqueadas, `CORS_ORIGINS` incorrecto, o `SameSite` mal configurado |
| 502 / timeout largo | Cold start de Render; esperar y recargar |
| Login correcto pero sin datos | BD vacía o usuario sin rol; revisar tablas en PostgreSQL |

### Comandos útiles (desde tu PC)

```powershell
# Health del API
curl https://ferragro-api.onrender.com/health

# Ver servicios en Render (requiere CLI instalada y login)
render services -o json --confirm
```

---

## 5. Cuidados para que no “caiga” o deje de funcionar

### Plan Free de Render

- El **API se duerme** sin uso → la primera visita del día puede ser lenta; no es caída permanente.
- La **BD gratuita** tiene fecha de expiración en el dashboard; renueva o migra a plan de pago antes de que expire.
- Límites de CPU/RAM: picos muy altos pueden reiniciar el servicio.

### Seguridad

1. **No subir** `.env`, contraseñas ni `DATABASE_URL` a GitHub.
2. **Rotar** `SECRET_KEY` solo si aceptas cerrar todas las sesiones activas.
3. **Restringir IP** de PostgreSQL: en Render → `ferragro-db` → quitar `0.0.0.0/0` si ya no necesitas migraciones desde cualquier IP; deja solo tu IP o acceso interno.
4. **Cambiar contraseñas** de usuarios admin tras el primer despliegue.
5. **Protección Vercel:** no activar SSO/password en Production si el sitio debe ser público.

### Cambios de configuración

| Si cambias… | También debes… |
|-------------|----------------|
| URL del API en Render | Actualizar `VITE_API_URL` en Vercel y redeploy front |
| Dominio nuevo del front | Actualizar `CORS_ORIGINS` en Render y redeploy API |
| Esquema SQL (`db/init/`) | Ejecutar scripts contra la BD de producción (sin seed) |
| `SECRET_KEY` | Redesplegar API; usuarios deberán volver a iniciar sesión |

### Backups y datos

- Export periódico con `pg_dump` usando la External Database URL (ver `docs/operacion_continuidad.md` si existe versión ampliada de backups).
- Antes de scripts destructivos en producción, **backup obligatorio**.

### Git y despliegue

- Trabajar en ramas y fusionar a `main` solo cuando el build local pase.
- Tras merge a `main`, verificar en Render y Vercel que el deploy terminó en **Live** / **Ready**.

### Monitoreo recomendado (opcional)

- Revisar `/health` con un monitor externo (UptimeRobot, etc.) cada 5–15 min para mantener el API despierto (consume cuota Free).
- Alertas por correo en Render/Vercel cuando un deploy falle.

---

## 6. Resumen de contacto entre piezas

```text
Usuario (navegador)
    → https://frontend-ferragro.vercel.app  (Vercel)
    → API: https://ferragro-api.onrender.com/api/v1/...  (Render)
    → BD: ferragro-db (PostgreSQL interno en Render, vía DATABASE_URL)
```

---

## 7. Documentos relacionados

| Archivo | Contenido |
|---------|-----------|
| `README.md` | Instalación local, arquitectura, despliegue inicial |
| `db/README.md` | Scripts SQL y migraciones |
| `.env.example` | Variables del backend |
| `frontend/.env.example` | Variables del frontend |
| `render.yaml` | Blueprint Render (BD + API) |
| `db/bootstrap-admin.ps1` | Crear o restablecer el primer Admin |
| `docs/operacion_continuidad.md` | Continuidad, backups, RPO/RTO (si aplica) |

---

*Última actualización según despliegue en Vercel + Render (marzo 2026). Si cambias nombres de servicios o dominios en los dashboards, actualiza las URLs de este documento.*
