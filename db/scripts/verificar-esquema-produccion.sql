-- Diagnostico: columnas que el API (SQLAlchemy) espera en produccion.
-- Idempotente, solo lectura + mensajes.

\echo '=== Columnas requeridas ==='

WITH required(table_name, column_name) AS (
  VALUES
    ('Proveedores', 'Estado'),
    ('Proveedores', 'SuspendidoEn'),
    ('Proveedores', 'EquiposDescarga'),
    ('Citas', 'IdBodega'),
    ('Citas', 'IdEquipoDescargaBodega'),
    ('Citas', 'IndiceEquipoProveedor'),
    ('Bodegas', 'EquiposDescarga'),
    ('UsuariosBodegas', 'IdDocumento'),
    ('EquiposDescargaBodega', 'Id')
)
SELECT r.table_name, r.column_name,
       CASE WHEN c.column_name IS NOT NULL THEN 'OK' ELSE 'FALTA' END AS estado
FROM required r
LEFT JOIN information_schema.columns c
  ON c.table_schema = 'public'
 AND c.table_name = r.table_name
 AND c.column_name = r.column_name
ORDER BY estado DESC, r.table_name, r.column_name;

\echo ''
\echo '=== Rol AdminBodega ==='
SELECT "Id", "Nombre" FROM "Rol" WHERE "Nombre" IN ('Admin', 'AdminBodega', 'Logistica', 'Proveedor') ORDER BY "Id";

\echo ''
\echo '=== Citas con datos incompletos ==='
SELECT
  COUNT(*) FILTER (WHERE "IdBodega" IS NULL) AS citas_sin_bodega,
  COUNT(*) FILTER (WHERE "IdEquipoDescargaBodega" IS NULL) AS citas_sin_equipo,
  COUNT(*) AS total_citas
FROM "Citas";

\echo ''
\echo '=== Proveedores sin Estado activo ==='
SELECT COUNT(*) AS proveedores_estado_null
FROM "Proveedores"
WHERE "Estado" IS NULL OR TRIM("Estado") = '';

\echo ''
\echo '=== Prueba SELECT (como el API) ==='
SELECT COUNT(*) AS citas_join_ok
FROM "Citas" c
JOIN "Proveedores" p ON p."IdNit" = c."IdProveedor"
JOIN "Bodegas" b ON b."Id" = c."IdBodega";
