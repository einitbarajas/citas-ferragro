-- =============================================================================
-- Usuarios: INSERT (Create)
-- "IdDocumento" debe cumplir el CHECK: solo dígitos, longitud 7–10.
-- =============================================================================

CREATE OR REPLACE FUNCTION usuarios_create(
  p_id_documento VARCHAR(30),
  p_nombre_completo VARCHAR(120),
  p_id_credencial INTEGER,
  p_id_rol INTEGER
)
RETURNS VARCHAR(30)
LANGUAGE plpgsql
AS $$
BEGIN
  INSERT INTO "Usuarios" (
    "IdDocumento",
    "NombreCompleto",
    "IdCredencial",
    "IdRol"
  )
  VALUES (
    p_id_documento,
    p_nombre_completo,
    p_id_credencial,
    p_id_rol
  );

  RETURN p_id_documento;
EXCEPTION
  WHEN unique_violation THEN
    RAISE EXCEPTION 'usuarios_create: documento o credencial duplicada -> %', SQLERRM
      USING ERRCODE = '23505';
  WHEN foreign_key_violation THEN
    RAISE EXCEPTION 'usuarios_create: IdCredencial o IdRol inválido -> %', SQLERRM
      USING ERRCODE = '23503';
  WHEN check_violation THEN
    RAISE EXCEPTION 'usuarios_create: validación CHECK fallida (documento 7–10 dígitos) -> %', SQLERRM
      USING ERRCODE = '23514';
  WHEN not_null_violation THEN
    RAISE EXCEPTION 'usuarios_create: %', SQLERRM
      USING ERRCODE = '23502';
  WHEN OTHERS THEN
    RAISE EXCEPTION 'usuarios_create: error [%] %', SQLSTATE, SQLERRM
      USING ERRCODE = SQLSTATE;
END;
$$;

COMMENT ON FUNCTION usuarios_create(VARCHAR, VARCHAR, INTEGER, INTEGER) IS 'Inserta un usuario interno y devuelve "IdDocumento".';
