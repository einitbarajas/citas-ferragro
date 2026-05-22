# Conectar GitHub con Vercel y Render

Objetivo: cada `git push` a `main` despliegue **frontend** (Vercel) y **API** (Render) sin depender de deploy manual.

---

## Resumen rápido

| Plataforma | Problema habitual | Solución |
|------------|-------------------|----------|
| **Vercel** | Proyecto sin «Connect Git Repository» | Instalar app de Vercel en GitHub **o** secreto `VERCEL_TOKEN` + workflow Actions |
| **Render** | Último deploy viejo (`10fe606`) con Auto-Deploy off o build fallido | Settings → Git + Auto-Deploy On + **Deploy Hook** en GitHub |

---

## 1) Vercel — enlace Git (recomendado en el panel)

1. Instala la app de GitHub: https://github.com/apps/vercel (acceso al repo `einitbarajas/citas-ferragro`).
2. Abre https://vercel.com/ferragro/frontend/settings/git
3. **Connect Git Repository** → `einitbarajas/citas-ferragro`
4. **Production Branch:** `main`
5. **Root Directory:** `frontend` (importante: el código Vite está en esa carpeta)
6. **Framework Preset:** Vite  
7. Variables **Production** (Settings → Environment Variables):
   - `VITE_API_URL` = `https://ferragro-api.onrender.com`
   - `VITE_API_PREFIX` = `/api/v1`
8. Guarda y haz **Redeploy** una vez.

Si «Connect» falla por permisos, usa el plan B (Actions) abajo.

### Plan B — GitHub Actions (ya en el repo)

Workflow: `.github/workflows/deploy-vercel-frontend.yml`

1. Crea token: https://vercel.com/account/tokens → **Create**
2. GitHub → `citas-ferragro` → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**
   - Nombre: `VERCEL_TOKEN`
   - Valor: el token
3. Cada push a `main` que cambie `frontend/**` desplegará a https://frontend-ferragro.vercel.app

IDs del proyecto (referencia, no son secretos): `frontend/.vercel/project.json.example`

---

## 2) Render — enlace Git + Auto-Deploy

1. Panel API: https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0
2. **Settings** → **Build & Deploy**:
   - **Repository:** `https://github.com/einitbarajas/citas-ferragro`
   - **Branch:** `main`
   - **Root Directory:** `backend`
   - **Auto-Deploy:** **On**
3. Si **Repository** está vacío: **Connect GitHub** → autoriza → elige el repo → guarda.
4. **Manual Deploy** → **Deploy latest commit** (una vez, para salir del commit `10fe606` del 15 mayo).
5. Verifica: https://ferragro-api.onrender.com/health  
   - `build_id` = valor en `backend/app/main.py` → `API_BUILD_ID`  
   - `render_git_commit` = primeros caracteres del último commit de `main`

### Deploy Hook (para GitHub Actions)

1. **ferragro-api** → **Settings** → **Deploy Hook** → **Create Hook** → copia URL.
2. GitHub → **Secrets** → `RENDER_DEPLOY_HOOK` = esa URL (si cambias el servicio, crea hook nuevo).
3. Workflow: `.github/workflows/deploy-render-api.yml` (falla si falta el secreto o el hook no responde 2xx).

**Nota:** El hook solo **pide** un deploy; si el build en Render **falla**, el servicio sigue en la versión anterior. Revisa **Events** → log del build.

---

## 3) Comprobar que todo quedó enlazado

```powershell
# API
Invoke-RestMethod https://ferragro-api.onrender.com/health | Select-Object -ExpandProperty data

# Debe coincidir con:
Select-String API_BUILD_ID backend/app/main.py
```

```powershell
git log -1 --oneline
# render_git_commit en /health debe empezar como el hash corto de ese commit
```

Frontend: https://frontend-ferragro.vercel.app (Ctrl+F5 si el navegador cachea JS).

---

## 4) Scripts locales

```powershell
.\scripts\conectar-git-produccion.ps1   # abre paneles y lista secretos
.\scripts\deploy-produccion.ps1         # push + hook + espera /health
```

---

*Mayo 2026 — proyecto `citas-ferragro`, equipo Vercel `ferragro`, servicio Render `ferragro-api`.*
