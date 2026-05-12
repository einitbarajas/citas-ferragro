CREATE OR REPLACE FUNCTION "FnRegistrarAuditoriaCitas"()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
  v_actor VARCHAR(30);
  v_accion VARCHAR(80);
  v_descripcion TEXT;
  v_id_cita INTEGER;
BEGIN
  /*
    Actor preferido: variable de sesion app.current_actor.
    Respaldo: proveedor de la cita (para altas realizadas por proveedor).
  */
  v_actor := NULLIF(current_setting('app.current_actor', true), '');
  IF v_actor IS NULL THEN
    IF TG_OP = 'DELETE' THEN
      v_actor := OLD."IdProveedor"::VARCHAR(30);
    ELSE
      v_actor := NEW."IdProveedor"::VARCHAR(30);
    END IF;
  END IF;

  IF TG_OP = 'INSERT' THEN
    v_accion := 'create_appointment';
    v_descripcion := 'Cita creada automaticamente por trigger';
    v_id_cita := NEW."Id";
  ELSIF TG_OP = 'UPDATE' THEN
    v_accion := 'update_appointment';
    v_descripcion := 'Cita actualizada automaticamente por trigger';
    v_id_cita := NEW."Id";
  ELSIF TG_OP = 'DELETE' THEN
    v_accion := 'delete_appointment';
    v_descripcion := 'Cita eliminada automaticamente por trigger';
    v_id_cita := OLD."Id";
  END IF;

  INSERT INTO "HistorialCambios" ("IdActor", "IdCita", "Accion", "Descripcion", "CreadoEn")
  VALUES (v_actor, v_id_cita, v_accion, v_descripcion, NOW());

  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS "TrgAuditoriaCitas" ON "Citas";
CREATE TRIGGER "TrgAuditoriaCitas"
AFTER INSERT OR UPDATE OR DELETE ON "Citas"
FOR EACH ROW
EXECUTE FUNCTION "FnRegistrarAuditoriaCitas"();

CREATE OR REPLACE FUNCTION "FnBloquearEdicionHistorial"()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  RAISE EXCEPTION 'El historial de auditoria es inmutable';
END;
$$;

DROP TRIGGER IF EXISTS "TrgBloquearUpdateHistorial" ON "HistorialCambios";
CREATE TRIGGER "TrgBloquearUpdateHistorial"
BEFORE UPDATE ON "HistorialCambios"
FOR EACH ROW
EXECUTE FUNCTION "FnBloquearEdicionHistorial"();

DROP TRIGGER IF EXISTS "TrgBloquearDeleteHistorial" ON "HistorialCambios";
CREATE TRIGGER "TrgBloquearDeleteHistorial"
BEFORE DELETE ON "HistorialCambios"
FOR EACH ROW
EXECUTE FUNCTION "FnBloquearEdicionHistorial"();
