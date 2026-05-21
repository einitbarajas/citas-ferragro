# Diccionario de transacciones — API Ferragro

Resumen de operaciones HTTP bajo `VITE_API_PREFIX` (por defecto `/api/v1`). Detalle en Swagger: `/docs`.

---

## Autenticación (`/api/auth` o `/api/v1/auth` según montaje)

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/register` | Registro proveedor (público) |
| POST | `/login` | JWT + cookie refresh |
| POST | `/refresh` | Nuevo access token |
| POST | `/logout` | Revoca sesión |

---

## Citas (`/appointments`)

| Método | Ruta | Rol típico |
|--------|------|------------|
| GET | `/` | Listado (modo week/day/month/list) |
| POST | `/` | Proveedor / Admin — requiere `warehouse_id` |
| PATCH | `/{id}/status` | Logística / Admin |
| PATCH | `/{id}/extend` | Logística / Admin |
| GET | `/available-slots` | Turnos libres por bodega y fecha |

---

## CRUD (`/crud`)

Usuarios, proveedores, roles, citas, historial, bodegas, franjas — según permisos de rol.

---

## Notificaciones (`/notifications`)

Listado, marcar leídas, contador no leídas.

---

## Admin (`/admin`)

Logs, eventos administrativos, liberación de correo.

---

## Salud

| Método | Ruta | Auth |
|--------|------|------|
| GET | `/health` | No |

---

*Sincronizar con `DICCIONARIO_TRANSACCIONES_FERRAGRO.xlsx` en revisiones mayores. Mayo 2026.*
