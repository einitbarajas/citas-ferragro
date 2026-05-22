# Manual de usuario — Portal Ferragro Citas

Guía rápida por rol. Producción: https://frontend-ferragro.vercel.app

---

## Acceso

| Rol | Cómo entrar |
|-----|-------------|
| **Admin** (global) | Solo cuenta creada por IT (`bootstrap-admin`); no usar «Registrarme» |
| **Administrador de bodega** | Alta por Admin en **Equipo** (rol *AdminBodega*), con una o más bodegas asignadas |
| **Logística** | Alta por Admin en **Equipo**, o registro si está habilitado |
| **Proveedor** | **Registrarme** con NIT, empresa y correo |

Si el login tarda mucho la primera vez del día, espere hasta ~1 minuto (servidor en la nube despertando).

---

## Conceptos clave

- **Bodega**: sede donde se descarga mercancía.
- **Muelle / equipo de descarga**: cada bodega tiene uno o más muelles (p. ej. «Carlos», «Rubén»). Las citas y la disponibilidad van **ligadas al muelle**, no solo a la bodega.
- **Franjas horarias**: turnos en los que se puede agendar. Se configuran en **Franjas horarias** eligiendo **bodega y muelle** (no es un solo calendario por bodega).
- **Equipos del proveedor** (camiones en paralelo): en **Configuraciones**, el proveedor indica cuántos vehículos puede tener a la vez; es distinto de los muelles de la bodega.

---

## Proveedor

1. Iniciar sesión.
2. **Agendar cita** (Inicio): elegir **bodega**, **muelle** de esa bodega, fecha y turno; describir el material.
   - Debe elegir **muelle** antes de ver días y turnos disponibles.
   - Puede tener varias citas el mismo día; con varios camiones (Configuraciones) puede agendar en paralelo según reglas del sistema.
   - La disponibilidad la define Admin o Administrador de bodega en **Franjas horarias** (por muelle).
3. **Mis citas**: lista, día o mes; cancelar según estado y plazos.
4. **Historial**: citas cerradas.
5. **Configuraciones**: perfil, contraseña y cantidad de **equipos de descarga** de su empresa (camiones).
6. **Notificaciones** (campana): cambios de fecha, hora o estado en sus citas.

Regla habitual: agendar con al menos **24 horas** de anticipación (configurable en el servidor).

---

## Logística

1. **Citas**: filtrar por día/semana/bodega (evitar «todas» si hay muchas citas).
2. **Revisión de citas**: abrir una cita y cambiar **estado** (revisada, finalizada, no presentada, cancelada, etc.).
3. **Buscar citas**: consultas y detalle.
4. **Reprogramar** o **extender duración** cuando aplique; el sistema evita solapamientos en el mismo muelle/bodega.
5. **Historial**: pestaña dedicada (no carga al entrar al panel).
6. **Configuraciones**: perfil y contraseña.
7. **Notificaciones**: citas nuevas o que vuelven a revisión.

Límite operativo: no más de **3** cambios de estado o **2** extensiones por cita (reglas de negocio).

*Logística no configura bodegas, muelles ni franjas.*

---

## Administrador de bodega

Rol intermedio: opera **solo las bodegas asignadas** al crear su usuario.

**Puede**

- Ver y gestionar citas de sus bodegas (Citas, Buscar, Revisión).
- **Bodegas**: cambiar cantidad de **Equipos** (muelles), **Nombres de muelles** y pulsar **Aplicar cambios** en cada fila (mensaje de confirmación en pantalla).
- **Franjas horarias**: definir turnos por **bodega y muelle**.

**No puede**

- Crear bodegas nuevas ni desactivarlas.
- Cambiar el nombre comercial de la bodega en pantalla (solo muelles y cantidad).
- Analítica global, **Proveedores**, **Auditoría** ni alta de usuarios Admin/Logística.

Manual en pantalla: botón **Manual guiado** (recorrido específico para este rol).

---

## Admin (global)

Todo lo de Logística en citas, más administración completa:

- **Equipo**: crear Admin, Logística o **Administrador de bodega** (asignando bodegas).
- **Bodegas**: crear sedes, ajustar muelles y nombres; **desactivar** bodega (solo Admin global).
- **Franjas horarias**: calendario por **bodega y muelle**; excepciones por fecha.
- **Proveedores**: alta, edición, suspensión y eliminación según reglas.
- **Auditoría** y **Analítica** / exportación Excel.
- Eliminar usuarios, proveedores o citas cuando corresponda.
- Liberar correo tras bajas (`release-email` o scripts SQL documentados).

---

## Notificaciones y correo

- **Campana** en el panel (todos los roles con sesión): avisos internos; el contador ámbar son no leídas.
- **Correo** (si SMTP está activo en Render): bienvenida, recuperar contraseña, cambios de estado de citas.

Comprobar: `GET .../health` → `"email_enabled": true`.

---

## Ayuda en pantalla

- **Manual guiado**: botón «Manual» / «Manual guiado»; el contenido depende del rol (Admin, Administrador de bodega, Logística o Proveedor).
- Tour de primera visita y mensajes de validación en español.
- Al guardar bodegas/muelles aparece un **mensaje de confirmación**; no hace falta recargar la página (F5).

---

*Para detalle técnico y despliegue, ver `GUIA_OPERACION_PRODUCCION.md`. Versión mayo 2026.*
