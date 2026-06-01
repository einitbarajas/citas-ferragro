# Correo en producción — solución definitiva

## Estado actual (lo que muestra tu captura)

| Campo | Significado |
|--------|-------------|
| `email_enabled: false` | **No se puede enviar correo** |
| `resend_ready: false` | Render **no tiene** `RESEND_API_KEY` cargada |
| `smtp_blocked_on_host: true` | Gmail SMTP **bloqueado** en Render free |

Tu archivo local `smtp-render.env` está bien; **el servidor nunca lo recibió** (o no se redeployó).

---

## Solución A — Automática (2 minutos, recomendada)

1. Crea API key en [Render → API Keys](https://dashboard.render.com/u/settings#api-keys) → copia `rnd_...`

2. En PowerShell, en la carpeta del proyecto:

```powershell
.\scripts\solucionar-correo-ya.ps1 -RenderApiKey "rnd_PEGA_TU_KEY_AQUI"
```

3. Espera a que diga **CORREO ACTIVO EN PRODUCCIÓN**

4. Abre https://ferragro-api.onrender.com/health → debe mostrar:
   - `resend_ready: true`
   - `email_enabled: true`
   - `email_provider: "resend"`

---

## Solución B — Manual (más rápida: solo 2 variables)

Si pegaste todo `smtp-render.env` y sigue igual, prueba **solo esto** (no hace falta tocar Gmail SMTP):

1. [Environment → ferragro-api](https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0/env)
2. **Add Environment Variable** (una por una):
   - `RESEND_API_KEY` = copia el valor de `smtp-render.env` en tu PC (empieza por `re_`)
   - `RESEND_SANDBOX` = `true`
3. **Save Changes**
4. Pestaña del servicio → **Manual Deploy** → **Deploy latest commit**
5. Espera 3–5 min y abre `/health` → debe decir `resend_ready: true`

> Con sandbox, el correo solo llega al Gmail de tu cuenta Resend.

---

## Solución C — Secret File (si B no basta)

**Importante:** en Render hay **dos sitios** distintos. Muchos pegan solo en "Environment" sin redeploy, o el archivo no se llama `smtp.env`.

### Paso 1 — Secret File (obligatorio)

1. Abre [ferragro-api → Secret Files](https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0/secrets)
2. Busca el archivo **`smtp.env`** (si no existe, créalo con ese nombre exacto)
3. Abre `smtp-render.env` en tu PC (raíz del proyecto)
4. **Copia todo** el contenido y pégalo en `smtp.env` en Render
5. **Save**

### Paso 2 — Variables sueltas (respaldo)

1. [Environment](https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0/env)
2. Añade o verifica:
   - `RESEND_API_KEY` = (la misma que en smtp-render.env)
   - `RESEND_SANDBOX` = `true`
3. **Save Changes**

### Paso 3 — Redeploy (obligatorio)

1. Pestaña **Manual Deploy**
2. **Deploy latest commit**
3. Espera 3–5 minutos

### Paso 4 — Comprobar

https://ferragro-api.onrender.com/health → `resend_ready: true`

Prueba **Olvidé mi contraseña** en https://citas.ferragro.vercel.app

---

## Sandbox Resend

Con `RESEND_SANDBOX=true` el correo solo llega al **Gmail de tu cuenta Resend** (no a cualquier dirección). Para enviar a todos los correos, verifica dominio en resend.com y pon `RESEND_SANDBOX=false`.

---

## Si sigue en false después de pegar

1. ¿Hiciste **Manual Deploy** después de guardar?
2. ¿El Secret File se llama exactamente **`smtp.env`**?
3. Ejecuta Solución A con `rnd_...` — es la forma más fiable.
