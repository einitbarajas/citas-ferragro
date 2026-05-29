# Arreglar citas + correo (2 minutos)

## Paso 1 — Render (obligatorio)

1. Abre [ferragro-api → Environment](https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0/env)
2. **Secret File** `smtp.env` → pega el contenido de `smtp-render.env` (raíz del repo)
3. **Save Changes**
4. **Manual Deploy** → *Deploy latest commit* (debe quedar `build_id: 2026-05-29-fast-recovery-v1`)

## Paso 2 — Comprobar

https://ferragro-api.onrender.com/health/deep

- `smtp_login_ok`: **true**
- `build_id`: **2026-05-29-fast-recovery-v1**

## Paso 3 — Vercel

Redeploy del frontend → en https://citas.ferragro.vercel.app pulsa **Ctrl+F5**

## Automático (siguiente vez)

En `.env` añade `RENDER_API_KEY=rnd_...` y ejecuta:

```powershell
.\scripts\arreglar-produccion-ahora.ps1
```
