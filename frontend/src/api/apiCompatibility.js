/** Respuesta 404 típica de FastAPI cuando la ruta no existe en el servidor desplegado. */
export function isApiRouteMissing(error) {
  if (error?.response?.status !== 404) return false;
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") {
    return detail.trim().toLowerCase() === "not found";
  }
  return false;
}

/** Bodegas inferidas de citas cuando el API aún no expone GET /crud/warehouses. */
export function deriveWarehousesFromAppointments(appointments) {
  const map = new Map();
  for (const appt of appointments || []) {
    const id = Number(appt?.warehouse_id);
    if (!Number.isFinite(id) || id <= 0) continue;
    if (map.has(id)) continue;
    const name = String(appt?.warehouse_name || "").trim() || `Bodega ${id}`;
    map.set(id, {
      id,
      name,
      address: null,
      active: true,
      sort_order: id,
      unload_teams: 1,
    });
  }
  return [...map.values()].sort(
    (a, b) => Number(a.sort_order) - Number(b.sort_order) || Number(a.id) - Number(b.id)
  );
}
