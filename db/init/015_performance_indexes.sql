-- Índices para listados y detección de solapamiento de citas (escala >1000 usuarios concurrentes moderados).
CREATE INDEX IF NOT EXISTS "IdxCitasBodegaFechaHora" ON "Citas"("IdBodega", "FechaHoraInicio");
CREATE INDEX IF NOT EXISTS "IdxCitasEstadoFechaHora" ON "Citas"("Estado", "FechaHoraInicio");
CREATE INDEX IF NOT EXISTS "IdxHistorialCambiosIdCitaAccion" ON "HistorialCambios"("IdCita", "Accion");
