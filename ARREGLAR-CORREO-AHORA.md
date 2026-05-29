# Arreglar correo en producción (2 minutos)

El API en Render **tiene una contraseña SMTP distinta** a la de tu `.env` local. Por eso la clave temporal se guarda en la BD pero **no llega el correo**.

## Pasos (obligatorio)

1. Abre [Render → ferragro-api → Environment](https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0/env)

2. **Secret Files** → archivo **`smtp.env`** (nombre exacto) → pega el contenido de `smtp-render.env` → **Save**

3. En **Environment Variables**, revisa que `SMTP_USER` y `SMTP_PASSWORD` coincidan con `smtp-render.env`  
   (si dudas, **borra** `SMTP_PASSWORD` y deja solo el Secret File).

4. **Manual Deploy** → **Deploy latest commit** (debe quedar `build_id`: `2026-05-29-smtp-secret-overlay-v1`)

5. Comprueba: https://ferragro-api.onrender.com/health/deep → `smtp_login_ok: true`

6. En https://citas.ferragro.vercel.app → **Olvidé mi contraseña** con `nataliabarajas412@gmail.com`

## Automático (si tienes API key de Render)

En `.env` añade una línea:

```env
RENDER_API_KEY=rnd_...
```

Luego:

```powershell
.\scripts\subir-smtp-ahora.ps1
```

## Automático (GitHub)

```powershell
gh auth login
.\scripts\instalar-smtp-github-secrets.ps1
```

Eso sube SMTP y dispara deploy desde Actions.
