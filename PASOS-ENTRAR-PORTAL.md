# Entrar al portal (producción) — checklist obligatorio

## Estado que debe verse cuando todo está bien

Abre en el navegador: https://ferragro-api.onrender.com/health

Debe decir un `build_id` reciente (el de `backend/app/main.py` → `API_BUILD_ID`, p. ej. `2026-05-22-calendar-per-team-v1`).

Si dice `2026-05-15-orphan-cleanup-b` → **el API en Render NO está actualizado**.

### Si en Events ves commit `10fe606` (15 mayo)

Ese **no es el código nuevo**. GitHub ya tiene **18 commits más nuevos** (login, correo, scripts SQL).

En Render debes desplegar el **último commit de `main`**, no el de mayo. Tras deploy correcto, `/health` mostrará `render_git_commit` empezando por `bbf359a` o más reciente (no `10fe606`).

---

## Por qué no se actualiza solo (muy común)

Subir código a GitHub **no cambia Render** si:

1. **Auto-Deploy está apagado** en el servicio `ferragro-api`.
2. El servicio **no está conectado** al repo `einitbarajas/citas-ferragro` (se creó manual sin Git).
3. El último deploy **falló en Build** (Render sigue sirviendo la versión anterior).

### Revisar en Render (2 min)

1. https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0  
2. Pestaña **Events** (o **Logs** del último deploy):
   - Si ves **Build failed** → abre el log y copia el error.
   - Si no hay deploys recientes → Git no está disparando deploys.
3. **Settings** → **Build & Deploy**:
   - **Repository:** `einitbarajas/citas-ferragro`
   - **Branch:** `main`
   - **Root Directory:** `backend` (importante)
   - **Auto-Deploy:** **On**

Si Repository está vacío: **Settings** → conecta GitHub y el repo, guarda, luego **Manual Deploy**.

### Deploy Hook (para que GitHub dispare deploy)

1. **ferragro-api** → **Settings** → **Deploy Hook** → **Create Hook** → copia la URL.  
2. GitHub → repo → **Settings** → **Secrets** → **Actions** → `RENDER_DEPLOY_HOOK` = esa URL.  
3. Cada push a `main` (carpeta `backend/`) disparará deploy (el workflow **falla** si el hook falta o el API no actualiza `build_id`).

### Vercel sin «Connect Git» en el panel

1. Secreto `VERCEL_TOKEN` en GitHub Actions.  
2. Workflow `deploy-vercel-frontend.yml` despliega en cada push a `frontend/`.  
3. Guía: [`docs/CONECTAR_GIT_VERCEL_RENDER.docx`](docs/CONECTAR_GIT_VERCEL_RENDER.docx)

```powershell
.\scripts\conectar-git-produccion.ps1
```

---

## Paso 1 — Desplegar API en Render (3 min)

1. https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0
2. Arriba a la derecha: **Manual Deploy** → **Deploy latest commit**  
   (No uses **Rollback** al commit `10fe606` del 15 de mayo.)
3. Esperar **Live** (si falla, mira **Events** → log del build).
4. Verificar `/health` con build nuevo (`2026-05-19-deploy-main` o posterior).

---

## Paso 2 — Arreglar la base de datos (2 min)

```powershell
cd "c:\dev\trabajo ferragro"
.\arreglar-portal.ps1
```

Pega la **External Database URL** (Render → ferragro-db → Connections).  
**No** escribas `db/scripts/ENTRAR-AHORA.sql` en PowerShell; ese archivo no se ejecuta así.

O en el panel: **ferragro-db** → **Connect** → PSQL → pegar todo `db/scripts/ENTRAR-AHORA.sql` → debe salir **1 fila** Admin.

---

## Paso 3 — Login

https://frontend-ferragro.vercel.app

| Campo | Valor |
|-------|--------|
| Correo | `ebarajas@ferragro.com` |
| Contraseña | `FerragroPortal2026!` |

No uses "Olvidé mi contraseña" hasta tener SMTP en Render.

---

## Alternativa: script en tu PC

Crea `.env.render.local` en la raíz del repo:

```
RENDER_DATABASE_URL=postgresql://ferragro:...@dpg-....oregon-postgres.render.com:5432/ferragro
```

(Copia desde Render → ferragro-db → Connections → External Database URL)

Luego:

```powershell
.\scripts\fix-render-admin.ps1
```
