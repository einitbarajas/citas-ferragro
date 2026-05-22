-- Corrige correo de proveedor CI (.test no es válido para EmailStr de Pydantic). Idempotente.

UPDATE "Credenciales"
SET "Correo" = 'pytest-proveedor-ci@example.com'
WHERE "Correo" = 'pytest-proveedor@ferragro.test';

UPDATE "Proveedores"
SET "CorreoEmpresa" = 'pytest-proveedor-ci@example.com'
WHERE "CorreoEmpresa" = 'pytest-proveedor@ferragro.test';
