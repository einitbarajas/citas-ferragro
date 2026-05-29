# Activar correo en producción (Render)

Vercel **no envía correos**; solo necesita `VITE_API_URL=https://ferragro-api.onrender.com` (ya configurado).

El SMTP vive en **Render → ferragro-api → Environment**.

## Opción A — Importar archivo (rápida)

1. En tu PC, genera el archivo (si no existe):
   ```powershell
   cd "c:\dev\trabajo ferragro"
   .\scripts\configurar-smtp-render.ps1
   ```
   (Sin API key solo crea `smtp-render.env` y abre el panel.)

2. Render → [ferragro-api → Environment](https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0/env)

3. **Add from .env** → elige `smtp-render.env` de la raíz del repo.

4. **Save Changes** (Render redeploy solo, ~3–5 min).

5. Verifica: https://ferragro-api.onrender.com/health  
   - `email_enabled`: **true**  
   - `smtp_host`: **smtp.gmail.com** (o tu servidor)

## Opción B — Secret file (alternativa)

1. Mismo contenido que `smtp-render.env`.
2. Environment → **Secret Files** → **Add Secret File**
3. Filename: **`smtp.env`**
4. Pega el contenido → Save (redeploy).

El API lee `/etc/secrets/smtp.env` al arrancar.

## Opción C — GitHub Actions (automatizar)

Secrets en GitHub (`Settings → Secrets → Actions`):

| Secret | Valor |
|--------|--------|
| `RENDER_API_KEY` | [API Keys Render](https://dashboard.render.com/u/settings#api-keys) |
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | cuenta remitente |
| `SMTP_PASSWORD` | contraseña de aplicación |
| `SMTP_FROM_EMAIL` | mismo remitente |
| `RENDER_DEPLOY_HOOK` | (opcional) Deploy Hook del servicio |

Ejecuta workflow **Sync SMTP to Render** en la pestaña Actions.

## Opción D — Script con API key

```powershell
cd "c:\dev\trabajo ferragro"
# Añade en .env (no se sube a Git): RENDER_API_KEY=rnd_...
.\scripts\configurar-smtp-render.ps1
# o: $env:RENDER_API_KEY = "rnd_..."; .\scripts\configurar-smtp-render.ps1
```

## Probar

1. https://frontend-ferragro.vercel.app → **Olvidé mi contraseña**
2. Revisa bandeja y spam.

## Si sigue en false

En `/health` mira `smtp_diag`:

```json
"smtp_diag": {
  "host_set": true,
  "user_set": true,
  "password_set": true,
  "from_email_set": true
}
```

Si alguno es `false`, falta esa variable en Render o el deploy no terminó.
