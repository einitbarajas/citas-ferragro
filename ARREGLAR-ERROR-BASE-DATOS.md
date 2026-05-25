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

El script aplica migraciones **013**–**023** (idempotentes) y las funciones CRUD. **No borra** citas ni proveedores (no usa `-Seed`).

Solo error `Proveedores.Estado`: ejecutar `db/scripts/fix-proveedores-estado.sql` en PSQL de Render.

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

### 4. Verificar que el esquema quedó bien

```powershell
cd "c:\dev\trabajo ferragro\db"
.\verificar-esquema-produccion.ps1
```

Todas las filas deben decir **OK** y `citas_join_ok` debe ser mayor que 0.

También puedes comprobar el API (debe responder sin 500):

```powershell
curl.exe -s "https://ferragro-api.onrender.com/health"
# build_id: 2026-05-22-prod-sync-v2
```

### 5. Si el portal sigue mostrando el toast

1. **Cerrar sesión** y **Ctrl+F5** (obligatorio tras migrar).
2. Revisar logs de **ferragro-api** (no solo ferragro-db): copia la línea `ERROR` más reciente.
3. Si `verificar-esquema-produccion.ps1` muestra todo OK pero el toast persiste, suele ser caché del navegador o sesión antigua; prueba ventana de incógnito.

### 6. Comprobar logs de PostgreSQL

En Render → ferragro-db → **Logs**: ya no deben salir `column ... does not exist`.

---

## Resumen

No es un fallo de Vercel ni del deploy del API: falta **actualizar el esquema de PostgreSQL en Render** con el script anterior. Tras ejecutarlo, el API y la BD deben coincidir; si no, usa `verificar-esquema-produccion.ps1`.
