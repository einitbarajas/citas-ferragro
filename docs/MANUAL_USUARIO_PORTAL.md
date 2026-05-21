# Manual de usuario — Portal Ferragro Citas

Guía rápida por rol. Producción: https://frontend-ferragro.vercel.app

---

## Acceso

| Rol | Cómo entrar |
|-----|-------------|
| **Admin** | Solo cuenta creada por IT (`bootstrap-admin`); no usar «Registrarme» |
| **Logística** | Alta por Admin en **Equipo**, o registro si está habilitado |
| **Proveedor** | **Registrarme** con NIT, empresa y correo |

Si el login tarda mucho la primera vez del día, espere hasta ~1 minuto (servidor en la nube despertando).

---

## Proveedor

1. Iniciar sesión.
2. **Agendar cita**: elegir **bodega**, **muelle/equipo de la bodega**, **tu equipo** (camión), fecha y turno; describir el material.
   - Puedes tener **varias citas el mismo día** y, con equipos distintos, **a la misma hora**.
   - La disponibilidad se consulta **por muelle**: cada uno tiene sus franjas horarias (Admin → Horarios, por equipo).
   - En **Configuraciones** defines cuántos equipos de descarga tiene tu empresa (camiones en paralelo).
3. Ver **Mis citas** (lista, día o mes).
4. **Cancelar** dentro de las reglas del sistema (estado y plazos).
5. **Perfil**: actualizar datos y contraseña.

Regla: debe agendar con al menos **24 horas** de anticipación (configurable en el servidor).

---

## Logística

1. Panel **Citas**: filtrar por día/semana/bodega (evitar «todas» si hay muchas citas).
2. Abrir una cita → cambiar **estado** (revisado, finalizada, no presentada, etc.).
3. **Reprogramar** o **extender duración** cuando aplique; el sistema evita solapamientos en la misma bodega.
4. **Proveedores**: consulta y edición (no eliminar salvo permisos Admin).
5. **Historial**: pestaña dedicada (no carga al entrar al panel).

Límite operativo: no más de **3** cambios de estado o **2** extensiones por cita (reglas de negocio).

---

## Admin

Todo lo de Logística, más:

- **Equipo**: crear Admin o Logística.
- **Franjas / bodegas**: configurar horarios por bodega y excepciones por fecha.
- **Eliminar** usuarios, proveedores o citas cuando corresponda.
- **Auditoría** y analítica / exportación Excel.
- Liberar correo tras bajas (`release-email` o scripts SQL documentados).

---

## Notificaciones y correo

- Campana en el panel: avisos internos.
- Correo (si SMTP está activo en Render): bienvenida, recuperar contraseña, cambios de estado de citas.

Comprobar: `GET .../health` → `"email_enabled": true`.

---

## Ayuda en pantalla

El panel incluye **tour guiado** (primera visita) y textos de validación en español.

---

*Para detalle técnico y despliegue, ver `GUIA_OPERACION_PRODUCCION.md`. Versión mayo 2026.*
