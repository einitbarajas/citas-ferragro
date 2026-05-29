# Correo / SMTP en producción

## Resumen

| Dónde | Gmail SMTP (`smtp-render.env`) |
|--------|--------------------------------|
| Tu PC (local) | **Sí funciona** |
| Render plan **free** | **No** (bloquean puerto 587) |
| Render plan **Starter** | **Sí** (sube `smtp-render.env`) |
| Render free + **Resend** | **Sí** (mismo flujo, por HTTPS) |

## Activar en 1 comando

```powershell
.\scripts\dejar-smtp-funcionando.ps1
```

Necesitas en `.env`:

- `RENDER_API_KEY=rnd_...` (Render → Account → API Keys)
- `RESEND_API_KEY=re_...` (Resend → **API Keys** solamente; **no** uses Domains con la URL de Render)

El script sube todo a Render (`smtp.env` + Resend) y despliega.

## Manual (si no tienes Render API key)

1. Render → ferragro-api → **Secret File** `smtp.env` → pega contenido de `smtp-render.env` **y** añade al final:

```env
RESEND_API_KEY=re_tu_clave
RESEND_SANDBOX=true
```

2. **Save** → **Manual Deploy**

3. https://ferragro-api.onrender.com/health → `email_provider: "resend"`, `resend_ready: true`

## Comprobar recuperar contraseña

https://citas.ferragro.vercel.app → `nataliabarajas412@gmail.com` → Olvidé mi contraseña.
