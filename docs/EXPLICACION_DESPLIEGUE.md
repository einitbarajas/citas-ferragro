# Por qué no se actualizaba solo — y qué hace cada pieza

## Las tres copias del código

| Lugar | Qué es |
|-------|--------|
| **Tu PC** | Donde programas (`c:\dev\trabajo ferragro`) |
| **GitHub** (`main`) | Copia central; Render y Vercel deberían leer de aquí |
| **Producción** | Vercel (pantalla) + Render (API) + PostgreSQL (datos) |

Actualizar GitHub **no cambia** producción hasta que **Vercel** y **Render** construyan y publiquen esa versión.

---

## Vercel (frontend)

- **Problema:** el proyecto no tenía «Connect Git Repository» (checklist 1/6).
- **Sin Git:** cada `git push` no hace nada en Vercel.
- **Solución A:** conectar repo en https://vercel.com/ferragro/frontend/settings/git (rama `main`, carpeta `frontend`).
- **Solución B:** workflow GitHub con secreto `VERCEL_TOKEN`, o comando local:

  ```powershell
  cd frontend
  npx vercel deploy --prod --yes
  ```

El agente puede desplegar Vercel así porque ya hay sesión `vercel login` en tu PC.

---

## Render (API)

- **Problema:** el último deploy **Live** era del **15 mayo** (commit `10fe606`), no el de hoy.
- **Síntoma:** `/health` devuelve `build_id: 2026-05-15-orphan-cleanup-b`.
- **Causas habituales:**
  1. Auto-Deploy apagado o deploy manual al commit viejo.
  2. **Build failed** en Events (Render sigue sirviendo la versión anterior).
  3. Deploy Hook en GitHub mal configurado o ausente (el workflow falla en «Trigger Render deploy»).

- **Solución inmediata:** Render → **Manual Deploy** → **Deploy latest commit** (commit reciente en `main`, p. ej. `f90d58d` o posterior).
- **Solución automática:** Deploy Hook + secreto `RENDER_DEPLOY_HOOK` en GitHub, o Auto-Deploy ON con repo conectado.

El agente **no puede** pulsar botones en tu panel Render ni crear secretos en tu cuenta GitHub sin que pegues el hook o el token **una vez**.

---

## Cómo comprobar que ya está bien

```text
GET https://ferragro-api.onrender.com/health
→ "build_id": "2026-05-22-prod-sync-v2"   (o el valor en backend/app/main.py)

https://frontend-ferragro.vercel.app  (Ctrl+F5)
```

---

## Un solo script en tu PC

```powershell
.\scripts\poner-produccion-actual.ps1
```

Pide la Deploy Hook URL si no está en `$env:RENDER_DEPLOY_HOOK`, despliega Vercel y espera el `/health` nuevo.

---

## Secretos GitHub (para el futuro)

https://github.com/einitbarajas/citas-ferragro/settings/secrets/actions

| Secreto | Para qué |
|---------|----------|
| `VERCEL_TOKEN` | Workflow `deploy-vercel-frontend.yml` |
| `RENDER_DEPLOY_HOOK` | Workflow `deploy-render-api.yml` |

Guía paso a paso: [`CONECTAR_GIT_VERCEL_RENDER.md`](CONECTAR_GIT_VERCEL_RENDER.md)
