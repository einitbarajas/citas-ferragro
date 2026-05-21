# Diccionario de datos — Ferragro Citas

Resumen de entidades PostgreSQL (esquema `public`). Nombres de tablas y columnas en español, como en `db/init/`.

---

## Bodegas

| Columna | Tipo | Descripción |
|---------|------|-------------|
| Id | SERIAL PK | Identificador |
| Nombre | VARCHAR(120) | Nombre único de la bodega |
| Direccion | VARCHAR(255) | Opcional |
| Activa | BOOLEAN | Si acepta nuevas citas |
| Orden | INTEGER | Orden en listados del portal |

Migración: `init/014_bodegas_franjas_flexibles.sql`. Seed: al menos «Bodega principal» si la tabla está vacía.

---

## Citas

| Columna | Tipo | Descripción |
|---------|------|-------------|
| Id | SERIAL PK | |
| IdProveedor | NUMERIC(9) FK | NIT del proveedor |
| **IdBodega** | INTEGER FK NOT NULL | Bodega de entrega (obligatorio desde 014) |
| DescripcionMaterial | TEXT | |
| FechaHoraInicio | TIMESTAMPTZ | Inicio en UTC |
| DuracionMinutos | INTEGER | Por defecto 90 |
| Estado | ENUM EstadoCita | sin_revision, revisado, finalizada, no_presentada, cancelado |

Índices: `015_performance_indexes.sql` (`IdBodega`, `FechaHoraInicio`).

Función CRUD: `citas_create(..., p_id_bodega DEFAULT NULL)` — si NULL, usa la bodega activa de menor Id.

---

## Proveedores, Usuarios, Credenciales, Rol

Sin cambios estructurales recientes respecto a `001_schema.sql`:

- **Credenciales**: correo + hash bcrypt; una credencial por usuario o proveedor.
- **Usuarios**: PK `IdDocumento`; FK a Rol y Credenciales.
- **Proveedores**: PK `IdNit` (10 dígitos); FK a Credenciales.

---

## Franjas horarias

| Tabla | Uso |
|-------|-----|
| FranjasPermitidasCita | Franjas por día de semana **y bodega** (014) |
| FranjasPermitidasCitaFecha | Excepciones por fecha concreta **y bodega** |

---

## HistorialCambios

Auditoría de cambios en citas. `IdActor` en texto (documento o NIT), sin FK estricta a Usuarios (003).

---

## Sesión y seguridad (011)

| Tabla | Uso |
|-------|-----|
| RefreshSessions | Cookies de renovación de token |
| LoginAttempts / LoginAudit | Bloqueo y auditoría de accesos |

---

## Referencias

- Scripts: `db/init/`, `db/database-crud/`
- Modelos Python: `backend/app/models/`

*Versión alineada con migraciones 001–015 (mayo 2026). Sincronizar con `DICCIONARIO_DATOS_FERRAGRO.docx` si se usa en entregables formales.*
