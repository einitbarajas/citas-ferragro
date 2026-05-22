# Error «Error de base de datos» en producción

## Qué significa

En los logs de **ferragro-db** (Render) aparece:

```text
ERROR: column Citas.IdBodega does not exist
```

| Pieza | Estado |
|-------|--------|
| **API (Render)** | Código nuevo (pide columna `IdBodega`) |
| **Front (Vercel)** | Actualizado |
| **PostgreSQL (Render)** | Esquema **viejo** (faltan migraciones 013–023) |

Por eso en Vercel:
- Toast **«Error de base de datos»**
- En Equipo no sale **Administrador de bodega** (falta rol en `Rol` + el API falla al cargar roles/citas)

En **localhost** funciona porque tu BD local sí tiene las migraciones.

---

## Solución (una vez, ~3 minutos)

### 1. Copiar la URL de la base de datos

1. https://dashboard.render.com  
2. Abre **ferragro-db** (PostgreSQL, no el web service).  
3. **Connections** → **External Database URL** → copiar (empieza por `postgresql://`).

### 2. Ejecutar migraciones en tu PC

PowerShell:

```powershell
cd "c:\dev\trabajo ferragro\db"
.\arreglar-esquema-produccion.ps1
```

Pega la URL cuando lo pida.

El script aplica **solo** migraciones `014`–`022` (idempotentes) y las funciones CRUD. **No borra** citas ni proveedores (no usa `-Seed`).

### Alternativa (todas las migraciones desde 001)

```powershell
cd "c:\dev\trabajo ferragro\db"
$env:DATABASE_URL = "postgresql://..."   # URL de Render
.\run-database-all.ps1
```

Sin `-Seed`.

### 3. Probar el portal

1. https://frontend-ferragro.vercel.app  
2. **Cerrar sesión**  
3. **Ctrl+F5**  
4. Iniciar sesión de nuevo  
5. **Equipo** → desplegable con **Administrador de bodega**

### Usuario «Administrador de bodega» (ya incluido en el script)

Tras `arreglar-esquema-produccion.ps1` queda un usuario listo para entrar:

| Campo | Valor |
|-------|--------|
| Correo | `admin.bodega@ferragro.com` |
| Contraseña | `FerragroPortal2026!` |
| Documento | `90000002` |
| Bodegas | Todas las activas en la BD |

**Alternativa sin PowerShell:** Render → ferragro-db → PSQL → pegar todo `db/scripts/ARREGLAR-TODO-PRODUCCION.sql`.

### 4. Comprobar logs

En Render → ferragro-db → **Logs**: ya no deben salir errores de `IdBodega`.

---

## Resumen

No es un fallo de Vercel ni del deploy del API: falta **actualizar el esquema de PostgreSQL en Render** con el script anterior.
