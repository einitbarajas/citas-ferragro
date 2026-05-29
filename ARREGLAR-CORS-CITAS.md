# Arreglar login en https://citas.ferragro.vercel.app

El API en Render estaba activo, pero **CORS** solo permitía `frontend-ferragro.vercel.app`, no `citas.ferragro.vercel.app`.

## Solución rápida (elige una)

### A) Desplegar el código nuevo (recomendado)

El backend ahora acepta en producción cualquier `https://*.ferragro.vercel.app` (incluye `citas` y `frontend-ferragro`).

1. Haz push de `main` a GitHub (o Manual Deploy en Render con el último commit).
2. Espera 3–5 min hasta que https://ferragro-api.onrender.com/health responda.
3. Abre https://citas.ferragro.vercel.app → **Ctrl+F5** → inicia sesión.

### B) Solo variable en Render (sin esperar al regex del código)

1. [Render → ferragro-api → Environment](https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0/env)
2. `CORS_ORIGINS` =

   ```
   https://frontend-ferragro.vercel.app,https://citas.ferragro.vercel.app
   ```

3. **Save** → **Manual Deploy**
4. Ctrl+F5 en el portal.

### C) Automático con API key

```powershell
$env:RENDER_API_KEY = "rnd_..."   # Render → Account Settings → API Keys
.\scripts\fix-cors-citas-render.ps1
```

## Comprobar que ya funciona

```powershell
curl.exe -s -I -X OPTIONS "https://ferragro-api.onrender.com/api/v1/auth/login" `
  -H "Origin: https://citas.ferragro.vercel.app" `
  -H "Access-Control-Request-Method: POST"
```

Debe aparecer `HTTP/1.1 200` y `access-control-allow-origin: https://citas.ferragro.vercel.app`.
