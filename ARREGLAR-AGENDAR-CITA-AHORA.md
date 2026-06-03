# Arreglar «Error interno del servidor» al Agendar cita

## Qué pasa (confirmado hoy)

El portal llama a **ferragro-api** en Render. Ese servidor **no tiene tu código nuevo**:

| | Producción (Render) | GitHub `main` |
|---|---------------------|---------------|
| `build_id` | `2026-06-02-email-logo-v2` | `2026-06-02-appointments-stable-v1` |
| commit | `789414c` (viejo) | `1a9f767` (arreglado) |

Log en Render al pulsar **Agendar cita**:

```text
AttributeError: 'Settings' object has no attribute 'resend_sandbox_inbox'
```

Ese fallo **ya está corregido en el repositorio**, pero **Render no ha desplegado** los últimos commits (auto-deploy no aplicó el cambio).

---

## Solución correcta (5 minutos) — Manual Deploy

1. Abre: https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0  
2. **Manual Deploy** → **Deploy latest commit** (no Rollback).  
3. Espera estado **Live** (5–8 min en plan free).  
4. Comprueba en el navegador:

   https://ferragro-api.onrender.com/health

   Debe mostrar:

   ```json
   "build_id": "2026-06-02-appointments-stable-v1"
   ```

   y `render_git_commit` debe empezar por `1a9f767` (no `789414c`).

5. En https://citas.ferragro.vercel.app → **Ctrl+F5** → vuelve a **Agendar cita**.

---

## Parche rápido SIN deploy (solo si no puedes desplegar ahora)

En Render → **Environment**:

- Cambia **`RESEND_SANDBOX`** de `true` a **`false`**
- Guarda (el servicio se reinicia solo)

Con sandbox desactivado, el código viejo **no toca** `resend_sandbox_inbox` y deja de hacer 500 al agendar.

**Nota:** los correos irán a destinatarios reales (no al inbox de prueba de Resend). Lo ideal sigue siendo el **Manual Deploy** arriba.

---

## Para que no vuelva a pasar

1. Render → **Settings** → **Deploy Hook** → copia la URL.  
2. En tu PC, en `.env` (no se sube a git):

   ```env
   RENDER_DEPLOY_HOOK=https://api.render.com/deploy/srv-...?key=...
   ```

3. Cada vez que quieras publicar la API:

   ```powershell
   cd "c:\dev\trabajo ferragro"
   .\scripts\desplegar-api-ahora.ps1
   ```

4. (Opcional) Mismo hook como secreto **`RENDER_DEPLOY_HOOK`** en GitHub Actions.

---

## Si Manual Deploy falla

En Render → **Events** → último evento:

- Si dice **Build failed**, abre el log y revisa la última línea de error (suele ser `pip` o variables de entorno).
- Confirma **Settings → Build & Deploy**: repo `einitbarajas/citas-ferragro`, rama `main`, **Root Directory** = `backend`, **Build Command** = `bash build.sh`.
