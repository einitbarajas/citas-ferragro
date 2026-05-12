# Base de Datos (PostgreSQL)

Esta carpeta contiene la configuración y scripts SQL de la base de datos, separada de `backend` y `frontend`.

## Despliegue recomendado (Windows / una sola pasada)

Desde la carpeta `db` (con la base `db_trabajo` ya creada y `DATABASE_URL` en el `.env` de la raíz del repo). En PowerShell hay que anteponer **`.\`** (punto-barra), no `\`:

```powershell
.\run-database-all.ps1
```

Eso ejecuta en orden:

1. `init/001_schema.sql` — tipos ENUM, tablas (`Rol`, `Credenciales`, `Usuarios`, `Proveedores`, `Citas`, `HistorialCambios`), índices y roles base (Admin, Logistica, Proveedor).
2. `init/002_audit_triggers.sql` — funciones y triggers de auditoría en citas.
3. `init/003_historial_id_actor_drop_fk.sql` — quita la FK antigua de `HistorialCambios.IdActor` hacia `Usuarios` si existía (idempotente; no borra datos).
4. `run-database-crud.ps1` — crea/reemplaza las funciones PL/pgSQL bajo `database-crud/`.

Datos de ejemplo (hace **TRUNCATE** de tablas de negocio; solo desarrollo):

```powershell
.\run-database-all.ps1 -Seed
```

### Scripts auxiliares

| Script | Uso |
|--------|-----|
| `PsqlDb.ps1` | Funciones internas (`Read-DatabaseUrlFromEnv`, `Resolve-PsqlExecutable`, `Invoke-FerragroSqlFile`). No ejecutar solo. |
| `run-database-crud.ps1` | Solo las funciones CRUD (tras tener esquema y triggers aplicados). |
| `run-database-all.ps1` | Esquema + parche + CRUD (+ seed opcional). |

Parámetros comunes: `-DatabaseUrl "postgresql://..."`, `-EnvFile "Ruta\.env"`.

### Nota para entorno Python en Windows

Si usas scripts de backend y aparece `Fatal error in launcher` con `pip`, evita usar `pip.exe` directo y ejecuta siempre el instalador con el intérprete del venv:

```powershell
.\.venv\Scripts\python.exe -m pip install -r ..\backend\requirements.txt
```

Esto evita problemas cuando el proyecto se movió de carpeta y el launcher de `pip` conserva una ruta antigua.

## Uso manual (sin `run-database-all.ps1`)

1. Crea la base `db_trabajo` (pgAdmin o `psql`).
2. Ejecuta en orden: `init/001_schema.sql`, `init/002_audit_triggers.sql`, `init/003_historial_id_actor_drop_fk.sql`, luego `.\run-database-crud.ps1`.
3. Opcional: `seeds/003_seed_data.sql` (trunca datos).

En el `.env` de la **raíz del repo**:

```env
DATABASE_URL=postgresql://postgres:TU_CONTRASEÑA@localhost:5432/db_trabajo
```

## Estructura

- `init/001_schema.sql`: tipos, tablas e índices; login unificado vía `Credenciales` enlazada a `Usuarios` o `Proveedores`.
- `init/002_audit_triggers.sql`: funciones y triggers de auditoría para citas.
- `init/003_historial_id_actor_drop_fk.sql`: migración ligera para bases creadas con FK antigua en `HistorialCambios.IdActor`.
- `seeds/003_seed_data.sql`: datos de demo (TRUNCATE).
- `database-crud/`: funciones PL/pgSQL por entidad (create/read/update/delete).
