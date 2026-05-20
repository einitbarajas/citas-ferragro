export function slotDurationMinutes(startLocal, endLocal) {
  const [sh, sm] = String(startLocal || "").split(":").map(Number);
  const [eh, em] = String(endLocal || "").split(":").map(Number);
  if (!Number.isFinite(sh) || !Number.isFinite(eh)) return 0;
  return eh * 60 + em - (sh * 60 + sm);
}

export function slotKey(slot) {
  return `${slot.start_local}|${slot.duration_minutes}`;
}

export function parseSlotKey(key) {
  const [start_local, durationRaw] = String(key || "").split("|");
  const duration_minutes = Number(durationRaw);
  if (!start_local || !Number.isFinite(duration_minutes)) return null;
  return { start_local, duration_minutes };
}

export function formatSlotLabel(slot) {
  const end = slot.end_local || "";
  const duration = slot.duration_minutes ?? slotDurationMinutes(slot.start_local, end);
  return `${slot.start_local} – ${end} (${duration} min)`;
}

export function normalizeAvailableSlots(sourceData) {
  const explicit = Array.isArray(sourceData?.available_slots) ? sourceData.available_slots : [];
  if (explicit.length > 0) {
    return explicit
      .map((s) => ({
        start_local: String(s.start_local || ""),
        end_local: String(s.end_local || ""),
        duration_minutes: Number(s.duration_minutes) || slotDurationMinutes(s.start_local, s.end_local),
      }))
      .filter((s) => s.start_local && s.duration_minutes >= 15);
  }
  const times = Array.isArray(sourceData?.available_times) ? sourceData.available_times : [];
  const fallbackMinutes = Number(sourceData?.slot_minutes || 90);
  return times.map((start_local) => ({
    start_local,
    end_local: "",
    duration_minutes: fallbackMinutes,
  }));
}

export function buildSlotsFromFranjas(franjas) {
  const out = [];
  (franjas || []).forEach((window) => {
    const start_local = String(window.start_local || "");
    const end_local = String(window.end_local || "");
    const duration_minutes =
      Number(window.duration_minutes) || slotDurationMinutes(start_local, end_local);
    if (!start_local || duration_minutes < 15) return;
    out.push({ start_local, end_local, duration_minutes });
  });
  return out.sort((a, b) => a.start_local.localeCompare(b.start_local));
}
