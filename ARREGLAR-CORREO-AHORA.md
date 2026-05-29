# Correo en producción — pasos correctos

## Error que viste en Resend

**No pongas** `https://ferragro-api.onrender.com` en **Domains**.  
Eso es la URL del API, no un dominio de correo. Resend lo marca en rojo.

## Opción rápida (5 minutos, sin DNS)

1. [resend.com/api-keys](https://resend.com/api-keys) → **Create API Key** → copia `re_...`
2. En tu PC, en la carpeta del proyecto:

```powershell
.\scripts\activar-correo-render.ps1
```

3. Pega la `re_...` cuando lo pida.
4. Pega tu **RENDER_API_KEY** (`rnd_...` desde [Render → Account → API Keys](https://dashboard.render.com/u/settings#api-keys))
5. El script sube variables y despliega solo.

Modo automático: usa `RESEND_SANDBOX=true` → envía desde `onboarding@resend.dev` a tu Gmail (`nataliabarajas412@gmail.com`). **No hace falta verificar dominio.**

## Para todos los correos (@ferragro.com, proveedores, etc.)

En Resend → **Domains** → nombre: **`ferragro.com`** (solo eso, sin https).

Quien administre el DNS de [ferragro.com](https://www.ferragro.com) debe añadir los registros TXT/MX que muestra Resend. Luego en Render:

```env
RESEND_API_KEY=re_...
RESEND_FROM_EMAIL=notificaciones@ferragro.com
RESEND_SANDBOX=false
```

## Alternativa Brevo (sin dominio, solo verificar Gmail)

1. [app.brevo.com](https://app.brevo.com) → **Senders** → añade `nataliabarajas412@gmail.com` → confirma el enlace en Gmail.
2. **SMTP & API** → API key `xkeysib-...`
3. `.\scripts\activar-correo-render.ps1` y pega la key de Brevo.

## Por qué Gmail SMTP no sirve en Render free

Render **bloquea** los puertos 587/465. Por eso `smtp-render.env` no funciona aunque esté bien pegado.

## Comprobar

https://ferragro-api.onrender.com/health debe mostrar:

- `email_provider`: `"resend"` o `"brevo"`
- `resend_ready` o `brevo_ready`: `true`
- `build_id`: contiene `email-https-v2`
