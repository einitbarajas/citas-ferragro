# Activar "Olvidé mi contraseña" en producción

## Automático (2 minutos)

1. En [Render → API Keys](https://dashboard.render.com/u/settings#api-keys) crea una key `rnd_...`
2. Añade en `.env` (no se sube a Git):

```env
RENDER_API_KEY=rnd_TU_KEY_AQUI
```

3. Ejecuta:

```powershell
.\scripts\dejar-correo-funcionando.ps1
```

El script sube `smtp-render.env` a Render, dispara deploy y espera `smtp_login_ok=true`.

## Alternativa con GitHub Actions

```powershell
gh auth login
.\scripts\publicar-smtp-github-secrets.ps1
```

Luego en GitHub → Actions → **Sync SMTP to Render** → Run workflow.

## Manual

1. Render → [ferragro-api → Environment](https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0/env)
2. Secret File `smtp.env` → pega el contenido de `smtp-render.env`
3. **Save** → **Manual Deploy**
4. Verifica: https://ferragro-api.onrender.com/health/deep → `smtp_login_ok: true`
