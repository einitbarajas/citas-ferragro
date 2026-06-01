# Correo en producción

## ¿Funciona ahora?

**NO** en https://ferragro-api.onrender.com hasta que subas Resend a Render.

Comprueba: https://ferragro-api.onrender.com/health → debe decir `resend_ready: true`.

La API key de Resend en tu `.env` **sí funciona** (envío de prueba OK). Falta copiarla al servidor.

## Activar en 1 comando (2 minutos)

1. Crea una API key en [Render → API Keys](https://dashboard.render.com/u/settings#api-keys) (`rnd_...`).

2. Ejecuta (sustituye la key):

```powershell
.\scripts\hacer-correo-funcionar.ps1 -RenderApiKey "rnd_TU_KEY_AQUI"
```

3. Cuando termine, abre `/health` y prueba **Olvidé mi contraseña** en https://citas.ferragro.vercel.app

## Manual (sin script)

Render → **ferragro-api** → **Environment** → pega el contenido de `smtp-render.env` (generado por el script) → **Save** → **Manual Deploy**.

Variables mínimas:

```env
RESEND_API_KEY=re_...
RESEND_SANDBOX=true
```

## Sandbox Resend

Con `RESEND_SANDBOX=true` los correos solo llegan al **Gmail de tu cuenta Resend** (normalmente el mismo que usas en el proyecto). Para cualquier otro correo, verifica dominio en resend.com.
