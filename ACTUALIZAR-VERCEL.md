# Actualizar Vercel (frontend) — paso a paso

Usa esto cuando el portal se ve viejo (no sale **Administrador de bodega**, mensajes de API desactualizado, etc.).

**Comprueba antes el API:** https://ferragro-api.onrender.com/health  
Debe tener `build_id` reciente (p. ej. `2026-05-22-prod-sync-v2`). Si no, arregla Render primero (`ARREGLAR-RENDER-AHORA.md`).

---

## Opción A — Desde tu PC (rápida, recomendada)

1. Abre PowerShell.
2. Ejecuta:

   ```powershell
   cd "c:\dev\trabajo ferragro\frontend"
   npx vercel login
   npx vercel deploy --prod --yes
   ```

3. Al terminar debe decir: `Aliased https://frontend-ferragro.vercel.app`
4. En el navegador abre https://frontend-ferragro.vercel.app y pulsa **Ctrl+F5** (recarga forzada).

---

## Opción B — Panel de Vercel (manual)

1. Entra a https://vercel.com/ferragro/frontend  
2. Pestaña **Deployments**.
3. El deployment más reciente de la rama `main` → menú **⋯** → **Redeploy**.
4. Marca **Production** → **Redeploy**.
5. Espera estado **Ready** (verde).
6. Abre https://frontend-ferragro.vercel.app → **Ctrl+F5**.

### Conectar Git (para que cada push actualice solo)

1. **Settings** → **Git** → **Connect Git Repository**.
2. Repo: `einitbarajas/citas-ferragro`.
3. **Production Branch:** `main`.
4. **Root Directory:** `frontend` (importante).
5. **Environment Variables** (Production):
   - `VITE_API_URL` = `https://ferragro-api.onrender.com`
   - `VITE_API_PREFIX` = `/api/v1`
6. Guarda y haz un **Redeploy**.

---

## Si no aparece «Administrador de bodega» en Equipo

El front ya lo trae; hace falta el **rol en la base de datos** de Render:

1. Render → **ferragro-db** → **Connect** → copia **External Database URL**.
2. En tu PC:

   ```powershell
   cd "c:\dev\trabajo ferragro"
   $env:DATABASE_URL = "postgresql://..."   # pegar URL
   .\db\run-database-all.ps1
   ```

   O solo el script `020`:

   ```powershell
   cd backend
   $env:PYTHONPATH = "."
   $env:DATABASE_URL = "postgresql://..."
   .\.venv\Scripts\python.exe scripts\apply_migration_020.py
   ```

3. Cierra sesión en el portal y vuelve a entrar.
4. **Equipo** → el desplegable debe mostrar:
   - Administrador  
   - Logística  
   - **Administrador de bodega**

Si ves **Administrador** dos veces, hay roles duplicados en la BD; el portal actualizado los agrupa por nombre.

---

## Comprobar que todo está al día

| Qué | URL / acción |
|-----|----------------|
| API | `/health` con `build_id` nuevo |
| Front | Portal con Ctrl+F5 |
| Rol | Equipo → «Administrador de bodega» + checkboxes de bodegas |
