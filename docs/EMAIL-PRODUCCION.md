# Correo transaccional Ferragro — producción

## Estado actual del canal

| Entorno | Transporte | Destinatarios |
|---------|------------|---------------|
| Render free + `RESEND_SANDBOX=true` | Resend HTTPS (`onboarding@resend.dev`) | Solo inboxes de prueba (cuenta Resend + `RESEND_SANDBOX_INBOX`) |
| Producción real | Resend con dominio verificado | Gmail, Outlook, Yahoo, iCloud, corporativos |

Render **bloquea SMTP 587/465** en plan free. El API usa **Resend** (o Brevo) por HTTPS.

## Diagnóstico rápido

```text
GET https://ferragro-api.onrender.com/health
GET https://ferragro-api.onrender.com/health/email
```

Campos clave:

- `resend_sandbox`: `true` = modo prueba (no llega a cualquier Gmail ajeno).
- `resend_sandbox_inbox_candidates`: inboxes donde sí llega en prueba.
- `production_delivery_mode`: `sandbox_testing` vs `domain_verified`.

## Activar entrega a cualquier proveedor (Gmail, Outlook, etc.)

1. En [Resend](https://resend.com/domains) agrega y verifica **`ferragro.com`** (o subdominio `citas.ferragro.com`).
2. Copia en DNS los registros que Resend muestra:
   - **SPF** (TXT)
   - **DKIM** (CNAME o TXT)
   - **DMARC** (TXT `_dmarc` recomendado: `v=DMARC1; p=none; rua=mailto:...`)
3. En Render → `ferragro-api` → Environment:

```env
RESEND_SANDBOX=false
RESEND_FROM_EMAIL=notificaciones@ferragro.com
RESEND_SANDBOX_INBOX=
```

4. Redeploy del API.
5. Prueba: `POST /api/v1/auth/maintenance/send-test-email` con `X-Maintenance-Token` y `template=recovery`.

## Modo prueba (mientras `RESEND_SANDBOX=true`)

- La recuperación de contraseña **sí genera** clave temporal en BD.
- El correo llega al **inbox de la cuenta Resend** (normalmente el mismo que `SMTP_USER` / Gmail de la API key).
- Revisa `resend_sandbox_inbox` en `/health/email`.

Variables recomendadas en `smtp.env` / Render:

```env
RESEND_SANDBOX=true
RESEND_SANDBOX_INBOX=tu-correo-de-cuenta-resend@gmail.com
```

Script local:

```powershell
$env:RENDER_API_KEY = "rnd_..."
.\scripts\configurar-smtp-render.ps1
```

## Flujos cubiertos por el código

| Flujo | Implementación |
|-------|----------------|
| Recuperación contraseña | `send_recovery_password_email` → Resend/SMTP |
| Bienvenida proveedor/staff | `dispatch_welcome_*` |
| Citas (crear/actualizar/cancelar/recordatorio) | `publish_appointment_notification` + email batch |
| Seguridad (bloqueo, intentos fallidos, cambio clave/correo) | `security_email.py` |
| Proveedor suspendido/reactivado | `dispatch_provider_account_notice` |

## Monitoreo

- Logs estructurados: `email_delivery ok|fail kind=...`
- Registro en memoria: `/health/email` → `recent_deliveries`, `delivery_stats`
- Resend dashboard: entregas, rebotes, dominio

## Pruebas obligatorias (checklist)

- [ ] `/health/email` → `can_deliver: true`
- [ ] Recuperación a Gmail de prueba
- [ ] Crear cita → correo staff/proveedor
- [ ] Recordatorio 24h (scheduler)
- [ ] HTML legible en móvil
- [ ] No en spam (tras dominio verificado y calentamiento)

## Seguridad

- No commitear `smtp-render.env` ni API keys.
- `MAINTENANCE_TOKEN` solo para pruebas puntuales.
- Contraseña temporal: un solo uso + cambio obligatorio en login.
