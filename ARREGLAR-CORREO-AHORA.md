# Correo en producción

## ¿Funciona ahora?

**NO** en https://ferragro-api.onrender.com hasta que subas Resend a Render.

Comprueba: https://ferragro-api.onrender.com/health → debe decir `resend_ready: true`.

La API key de Resend en tu `.env` **sí funciona** (envío de prueba OK). Falta copiarla al servidor.

## Activar en 1 comando (2 minutos)

> Si tenías `render login`, el token CLI **caduca** (~2 semanas). Si el script falla con 401, crea una **API key** nueva (no caduca).

1. Crea una API key en [Render → API Keys](https://dashboard.render.com/u/settings#api-keys) (`rnd_...`).

2. Ejecuta (sustituye la key):

```powershell
.\scripts\hacer-correo-funcionar.ps1 -RenderApiKey "rnd_TU_KEY_AQUI"
```

3. Cuando termine, abre `/health` y prueba **Olvidé mi contraseña** en https://citas.ferragro.vercel.app

## Manual (sin API key de Render)

```powershell
.\scripts\subir-resend-render.ps1
```

(Copia `smtp-render.env` al portapapeles y abre el panel de Render.)

1. [Environment ferragro-api](https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0/env) → **Add from .env** → pegar (Ctrl+V) o elegir `smtp-render.env`
2. **Save Changes**
3. **Manual Deploy** → último commit de `main`
4. Comprueba `/health` → `resend_ready: true`

Variables mínimas:

```env
RESEND_API_KEY=re_...
RESEND_SANDBOX=true
```

## Sandbox Resend

Con `RESEND_SANDBOX=true` los correos solo llegan al **Gmail de tu cuenta Resend** (normalmente el mismo que usas en el proyecto). Para cualquier otro correo, verifica dominio en resend.com.
