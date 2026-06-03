# Arreglar Render AHORA (API desactualizado)

## Qué ves

- `/health` → `"build_id":"2026-06-02-email-logo-v2"` y `render_git_commit` = `789414c` (**viejo**)
- El portal muestra: *«El servidor del API en Render está desactualizado…»*
- `GET /api/v1/crud/warehouses` → **404** (esa ruta no existe en el API del 15 mayo)

El **frontend (Vercel) está bien**. Falta publicar el **backend (Render)**.

---

## Paso 1 — Render: deploy del último código (5 min)

1. Abre: https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0  
2. Pestaña **Events** (arriba). Mira el evento más reciente:
   - Si dice **Build failed** → clic en el evento → copia las **últimas 20 líneas** del log (para soporte).
   - Si el último **Live** es del **15 mayo** (`10fe606`) → sigue al paso 3.
3. Botón negro **Manual Deploy** → elige **Deploy latest commit**  
   - **NO** uses **Rollback**  
   - **NO** elijas un commit del 15 de mayo
4. Espera hasta **Live** (verde). En Free puede tardar 5–8 min.
5. Comprueba en el navegador:

   https://ferragro-api.onrender.com/health

   Debe decir:

   ```json
   "build_id": "2026-06-02-appointments-stable-v1"
   ```

   y ya no solo dos campos; verás también `email_enabled`, etc.

---

## Paso 2 — Settings (para que no vuelva a pasar)

**Settings → Build & Deploy**

| Campo | Valor correcto |
|--------|----------------|
| Repository | `einitbarajas/citas-ferragro` |
| Branch | `main` |
| Root Directory | `backend` |
| Build Command | `pip install --upgrade pip && pip install -r requirements-prod.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Auto-Deploy | **On** |

Guarda cambios.

---

## Paso 3 — Deploy Hook + GitHub (automático en cada push)

1. Render → **Settings** → **Deploy Hook** → **Create Hook** → copia la URL.  
2. GitHub → https://github.com/einitbarajas/citas-ferragro/settings/secrets/actions  
3. Secreto **`RENDER_DEPLOY_HOOK`** = esa URL (crear o **actualizar** si ya existía una vieja).  
4. En tu PC (opcional, una vez):

   ```powershell
   [Environment]::SetEnvironmentVariable("RENDER_DEPLOY_HOOK", "PEGAR_URL_AQUI", "User")
   ```

5. Prueba:

   ```powershell
   cd "c:\dev\trabajo ferragro"
   .\scripts\poner-produccion-actual.ps1
   ```

---

## Paso 4 — Portal

1. https://frontend-ferragro.vercel.app  
2. **Ctrl+F5**  
3. Entra como Admin → **Bodegas** → prueba **Agregar bodega**

Si `/health` ya tiene el `build_id` nuevo y sigue el error, escribe qué dice **Events** en Render.

---

## Si el build falla en Render (común)

Copia el error del log. Causas típicas:

- **Root Directory** vacío o `frontend` (debe ser `backend`).
- Falta `requirements-prod.txt` en el commit desplegado (usa **latest commit** de `main`).
- Límite de memoria en plan Free (reintenta deploy).

Commit actual en GitHub: revisa https://github.com/einitbarajas/citas-ferragro/commits/main
