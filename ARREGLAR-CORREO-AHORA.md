# Por qué no llega el correo (y cómo arreglarlo)

## Causa real

**Render plan free bloquea los puertos SMTP (25, 465 y 587).**  
Gmail funciona en tu PC, pero el servidor en Render **no puede conectar** a `smtp.gmail.com`. Por eso `smtp_login_ok: false` y el mensaje *“no se pudo enviar el correo”*.

No es un bug del front ni del typo del correo (usa `nataliabarajas412@gmail.com`).

## Solución recomendada: Resend (gratis, HTTPS)

1. Crea cuenta en [resend.com](https://resend.com) (plan free).
2. **Domains** o **Emails** → verifica el remitente `nataliabarajas412@gmail.com` (te llega un enlace de confirmación).
3. **API Keys** → crea una key (`re_...`).
4. En [Render → ferragro-api → Environment](https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0/env) añade:

```env
RESEND_API_KEY=re_xxxxxxxx
RESEND_FROM_EMAIL=nataliabarajas412@gmail.com
```

5. **Save** → **Manual Deploy** (o espera auto-deploy de `main`).
6. Comprueba: https://ferragro-api.onrender.com/health → `email_provider: "resend"`, `resend_ready: true`
7. Prueba **Olvidé mi contraseña** en citas.

## Alternativa: plan de pago en Render

Si subes **ferragro-api** a un plan de pago (Starter), SMTP Gmail vuelve a funcionar con `smtp-render.env` en Secret File `smtp.env`.

## Qué ya no sirve solo

- Pegar `smtp-render.env` en Render **sin Resend ni plan de pago** → seguirá fallando (puertos bloqueados).
- Más cambios de contraseña de aplicación Gmail → solo ayuda en local, no en Render free.
