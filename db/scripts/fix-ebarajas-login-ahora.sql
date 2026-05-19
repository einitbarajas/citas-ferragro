-- Pega y ejecuta TODO en Render → ferragro-db → Connect (PSQL).
-- Correo: ebarajas@ferragro.com | Contraseña: FerragroPortal2026!

UPDATE "Credenciales" c
SET "HashContrasena" = '$2b$12$aUcXWqjg4WLU0Jcc77RmRevmIG/NfKrJgn.j3HXm9A14LndZm8Xni',
    "Correo" = 'ebarajas@ferragro.com'
FROM "Usuarios" u
JOIN "Rol" r ON r."Id" = u."IdRol"
WHERE u."IdCredencial" = c."IdCredencial"
  AND u."IdDocumento" = '90000001'
  AND r."Nombre" = 'Admin';

UPDATE "Credenciales" c
SET "HashContrasena" = '$2b$12$aUcXWqjg4WLU0Jcc77RmRevmIG/NfKrJgn.j3HXm9A14LndZm8Xni'
WHERE lower(c."Correo") = lower('ebarajas@ferragro.com');

DELETE FROM "IntentosLogin" il
USING "Credenciales" c
WHERE il."IdCredencial" = c."IdCredencial"
  AND lower(c."Correo") = lower('ebarajas@ferragro.com');

DELETE FROM "EstadoResetContrasena" e
USING "Credenciales" c
WHERE e."IdCredencial" = c."IdCredencial"
  AND lower(c."Correo") = lower('ebarajas@ferragro.com');

SELECT c."Correo", r."Nombre" AS rol, u."IdDocumento"
FROM "Usuarios" u
JOIN "Credenciales" c ON c."IdCredencial" = u."IdCredencial"
JOIN "Rol" r ON r."Id" = u."IdRol"
WHERE lower(c."Correo") = lower('ebarajas@ferragro.com');
