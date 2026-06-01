# Correo / SMTP en producción

## Diagnóstico rápido

Abre: https://ferragro-api.onrender.com/health

| Campo | Qué significa |
|--------|----------------|
| `email_enabled: false` | **No se envían correos** (citas, recuperar contraseña, etc.) |
| `email_provider: "smtp"` + `resend_ready: false` | Render intenta Gmail y **falla** (plan free bloquea puerto 587) |
| `email_provider: "resend"` + `resend_ready: true` | Correo operativo por HTTPS |

Diagnóstico completo: https://ferragro-api.onrender.com/health/deep  
(`smtp_login_ok: false` en Render free = normal sin Resend)

## Por qué ves notificaciones en el panel pero no en el correo

Las notificaciones **in-app** se guardan en la base de datos.  
Los **correos** salen por otro canal (SMTP o Resend). En Render free el SMTP de Gmail **no funciona**; hace falta **Resend** o **Brevo**.

## Activar en 1 comando

1. En `.env` añade: `RENDER_API_KEY=rnd_...` (Render → Account → API Keys)
2. Tu `smtp-render.env` ya debe tener `RESEND_API_KEY=re_...`

```powershell
.\scripts\subir-resend-render.ps1
```

O:

```powershell
.\scripts\activar-correo-render.ps1 -ResendKey "re_..." -RenderApiKey "rnd_..."
```

3. Tras el deploy, `/health` debe mostrar:
   - `email_enabled: true`
   - `email_provider: "resend"`
   - `resend_ready: true`

## Manual (sin API key de Render)

1. Render → **ferragro-api** → **Environment** (o Secret File `smtp.env`)
2. Añade (desde tu `smtp-render.env`):

```env
RESEND_API_KEY=re_tu_clave
RESEND_SANDBOX=true
```

3. **Save** → **Manual Deploy**

## Importante: modo sandbox de Resend

Con `RESEND_SANDBOX=true` solo llegan correos al **mismo Gmail con el que creaste la cuenta Resend**.  
Si el proveedor usa otro correo, no recibirá nada hasta que:

- verifiques un dominio en [resend.com](https://resend.com) y pongas `RESEND_SANDBOX=false`, o  
- uses **Brevo** (`BREVO_API_KEY`), o  
- subas Render a plan **Starter** y uses Gmail SMTP.

## Comprobar

1. `/health` → `email_enabled: true`
2. Crear una cita como proveedor (correo del proveedor = cuenta Resend si estás en sandbox)
3. O **Olvidé mi contraseña** en https://citas.ferragro.vercel.app

## Resumen

| Dónde | Gmail SMTP |
|--------|------------|
| Tu PC (local) | Sí |
| Render plan **free** | No (bloquean 587) |
| Render free + **Resend** | Sí (HTTPS) |
| Render plan **Starter** | Sí |
