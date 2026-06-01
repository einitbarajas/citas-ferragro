# Informe: sistema de correo transaccional Ferragro

**Fecha:** 2026-06-01  
**Build:** `2026-06-01-email-delivery-v1`  
**API:** https://ferragro-api.onrender.com  
**Panel:** https://citas.ferragro.vercel.app  

---

## 1. Resumen ejecutivo

| Área | Estado | Notas |
|------|--------|--------|
| Código de envío | Mejorado | Reintentos, logs, enlaces al panel, `/health/email` |
| Producción Render | **Bloqueado** | Sin `RESEND_API_KEY` en servidor; SMTP Gmail no funciona en plan free |
| Pruebas reales multi-proveedor | **Pendiente de config** | Requiere dominio verificado en Resend/Brevo |
| Recuperación contraseña | Código listo | Usa **contraseña temporal** (no magic link) |

**Conclusión:** El software está preparado; el fallo actual es **configuración en Render**, no lógica de plantillas.

---

## 2. Problemas encontrados

### 2.1 Crítico — Render sin Resend (producción)

Evidencia (`GET /health`):

```json
{
  "email_provider": "smtp",
  "resend_ready": false,
  "smtp_login_ok": false,
  "render_smtp_blocked_hint": "Render free bloquea SMTP..."
}
```

Render plan **free** bloquea puerto 587. Las credenciales Gmail existen pero **no pueden enviar**.

### 2.2 Recuperación de contraseña

- El flujo guardaba la clave temporal pero fallaba el envío (mismo bloqueo SMTP).
- No existen **enlaces mágicos** (`/reset?token=...`); el diseño actual envía la clave en el cuerpo del correo (válido y común, distinto a “enlace seguro”).

### 2.3 Notificaciones vs correo

Las notificaciones **in-app** funcionan sin SMTP. Los usuarios pueden creer que “el correo funciona” cuando solo ven el panel.

### 2.4 Resend sandbox

Con `RESEND_SANDBOX=true`, Resend solo entrega al **correo de la cuenta Resend**. No sirve para probar Gmail/Outlook/Yahoo de terceros hasta verificar dominio.

### 2.5 Recordatorios 24 h

`reminder_scheduler.py` **no envía email** (solo BD). Fuera del alcance actual salvo que se pida explícitamente.

---

## 3. Correcciones realizadas (código)

| Cambio | Archivo |
|--------|---------|
| Módulo unificado con reintentos y logs | `backend/app/services/email_delivery.py` |
| Avisos de cita con reintentos | `email_dispatch.py` → `send_notification_email_with_retry` |
| Recuperación vía Resend + reintentos | `mailer.py`, `email_dispatch.py` |
| Botón/enlace al panel en HTML y texto | `mailer.py` (`panel_cta_*`, `PUBLIC_PANEL_URL`) |
| Health honesto (`email_enabled` real) | `main.py` `/health` |
| Diagnóstico de flujos | `main.py` `/health/email` |
| Envío de prueba (maintenance) | `auth.py` `POST /api/auth/maintenance/send-test-email` |
| Script de prueba | `scripts/probar-correo-completo.ps1` |
| Tests unitarios | `backend/tests/test_email_delivery.py` |

---

## 4. Mapa de correos por objetivo

| Objetivo | Función | Disparador |
|----------|---------|------------|
| Cita nueva / revisión | `notify_staff_review_needed` | Crear cita, reprogramar |
| Cita actualizada / cancelada (staff) | `notify_provider_appointment_updated` | PATCH status, extend, PUT crud |
| Cancelación por proveedor | `notify_staff_provider_cancelled` | POST provider-cancel |
| Recuperar contraseña | `send_recovery_password_email` | POST forgot-password |
| Suspender proveedor | `dispatch_provider_account_notice` (suspended) | POST suspend — **incluye motivo** |
| Reactivar / eliminar / purgar | mismo helper | acciones CRUD |
| Bienvenida proveedor/staff | `dispatch_welcome_*` | registro / alta admin |

Todos usan `send_branded_email` → Resend / Brevo / SMTP según entorno.

---

## 5. SPF, DKIM, DMARC y entregabilidad

| Modo | Gmail/Outlook/Yahoo/etc. | Spam |
|------|--------------------------|------|
| Gmail SMTP local | Sí | Depende de reputación Gmail |
| Render free + Gmail | **No** | N/A |
| Resend **sandbox** | Solo cuenta Resend | N/A |
| Resend **dominio verificado** | Sí | Mejor (DKIM/SPF gestionados por Resend) |
| Brevo con remitente verificado | Sí | Similar |

**Recomendación producción:**

1. Verificar dominio `ferragro.com` (o subdominio `citas.ferragro.com`) en [resend.com/domains](https://resend.com/domains).
2. Publicar registros DNS que indique Resend (SPF + DKIM).
3. Activar DMARC en modo `p=none` → luego `quarantine` cuando estable.
4. `RESEND_SANDBOX=false` y `RESEND_FROM_EMAIL=noreply@tudominio.com`.

---

## 6. Pruebas obligatorias — plan y estado

### 6.1 Automáticas (local)

```bash
cd backend
python -m pytest tests/test_email_utils.py tests/test_email_delivery.py tests/test_notification_service_unit.py -q
```

### 6.2 Diagnóstico producción (sin enviar)

```powershell
Invoke-RestMethod https://ferragro-api.onrender.com/health/email
```

### 6.3 Envío real (tras configurar Render)

```powershell
# 1. Subir Resend
.\scripts\configurar-smtp-render.ps1

# 2. Esperar deploy con build_id 2026-06-01-email-delivery-v1

# 3. Prueba
.\scripts\probar-correo-completo.ps1 -Email "tu@gmail.com" -MaintenanceToken "TOKEN"
```

| Prueba | Cómo | Estado |
|--------|------|--------|
| Gmail | `-Email xxx@gmail.com` | Pendiente config Render |
| Outlook | `-Email xxx@outlook.com` | Pendiente |
| Yahoo | `-Email xxx@yahoo.com` | Pendiente |
| iCloud | `-Email xxx@icloud.com` | Pendiente |
| Proton | `-Email xxx@proton.me` | Pendiente (puede filtrar más) |
| Olvidé contraseña | UI o template `recovery` | Pendiente |
| Cita crear/actualizar/cancelar | Flujo UI + revisar bandeja | Pendiente |
| Suspensión proveedor | Admin suspende + motivo en correo | Pendiente |
| Enlaces en correo | Botón → `https://citas.ferragro.vercel.app` | Implementado en plantilla |
| HTML móvil | Tabla 640px responsive básica | Implementado |

---

## 7. Acción requerida (operaciones)

```powershell
# En .env
RENDER_API_KEY=rnd_...

.\scripts\configurar-smtp-render.ps1
```

Verificar:

- `/health` → `email_enabled: true`, `email_provider: "resend"`
- Olvidé contraseña en https://citas.ferragro.vercel.app

---

## 8. Recuperación de contraseña — aclaración de diseño

| Esperado (enunciado) | Implementado |
|----------------------|--------------|
| Enlace seguro único | **No** — contraseña temporal de 10 caracteres |
| Caducidad | Cooldown 60 s entre solicitudes; debe cambiar clave al entrar |
| Seguridad | Hash en BD; clave no reutilizable tras `change-password` |

Para magic links haría falta un desarrollo aparte (`reset_token`, expiración, URL firmada).

---

## 9. Evidencia de despliegue

Tras `git push`, comprobar:

```
GET /health → build_id: "2026-06-01-email-delivery-v1"
GET /health/email → can_deliver: true (solo si Resend configurado)
```

**Estado al redactar este informe:** producción seguía en commit antiguo sin Resend (`render_git_commit` anterior a estos cambios).

---

## 10. Archivos de referencia

- `ARREGLAR-CORREO-AHORA.md` — activación rápida Resend  
- `scripts/configurar-smtp-render.ps1` — subida automática a Render  
- `scripts/probar-correo-completo.ps1` — diagnóstico + prueba  
