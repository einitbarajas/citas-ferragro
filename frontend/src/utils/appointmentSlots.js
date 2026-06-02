export function slotDurationMinutes(startLocal, endLocal) {
  const [sh, sm] = String(startLocal || "").split(":").map(Number);
  const [eh, em] = String(endLocal || "").split(":").map(Number);
  if (!Number.isFinite(sh) || !Number.isFinite(eh)) return 0;
  return eh * 60 + em - (sh * 60 + sm);
}

function normalizeLocalTime(value) {
  const raw = String(value || "").trim();
  const [hhRaw, mmRaw] = raw.split(":");
  const hh = Number(hhRaw);
  const mm = Number(mmRaw);
  if (!Number.isFinite(hh) || !Number.isFinite(mm)) return "";
  return `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`;
}

function timeToMinutes(hhmm) {
  const [hh, mm] = String(hhmm || "").split(":").map(Number);
  if (!Number.isFinite(hh) || !Number.isFinite(mm)) return NaN;
  return hh * 60 + mm;
}

/** Quita turnos que son solo trozos de 60 min dentro de una franja larga (API antiguo). */
function dropSlotsContainedInAnother(slots) {
  const list = Array.isArray(slots) ? slots : [];
  if (list.length < 2) return list;
  return list.filter((slot) => {
    const start = timeToMinutes(slot.start_local);
    const end = start + Number(slot.duration_minutes);
    if (!Number.isFinite(start) || !Number.isFinite(end)) return false;
    return !list.some((other) => {
      if (other === slot) return false;
      const oStart = timeToMinutes(other.start_local);
      const oEnd = oStart + Number(other.duration_minutes);
      if (!Number.isFinite(oStart) || !Number.isFinite(oEnd)) return false;
      const contained = oStart <= start && oEnd >= end;
      const strict = oStart < start || oEnd > end;
      return contained && strict;
    });
  });
}

export function slotFingerprint(slot) {
  const start_local = normalizeLocalTime(slot.start_local);
  const end_local = normalizeLocalTime(slot.end_local);
  const duration_minutes =
    Number(slot.duration_minutes) ||
    (end_local ? slotDurationMinutes(start_local, end_local) : 0);
  return `${start_local}|${end_local}|${duration_minutes}`;
}

function filterSlotsToPublishedOnly(slots, published) {
  const cleaned = dedupeSlots(slots);
  const publishedList = dedupeSlots(published);
  if (publishedList.length === 0) return cleaned;
  const allowed = new Set(publishedList.map((s) => slotFingerprint(s)));
  return cleaned.filter((s) => allowed.has(slotFingerprint(s)));
}

function dedupeSlots(slots) {
  const dedupe = new Map();
  (slots || []).forEach((slot) => {
    const start_local = normalizeLocalTime(slot.start_local);
    const end_local = normalizeLocalTime(slot.end_local);
    const duration_minutes =
      Number(slot.duration_minutes) ||
      (end_local ? slotDurationMinutes(start_local, end_local) : 0);
    if (!start_local || !end_local || !Number.isFinite(duration_minutes) || duration_minutes < 15) {
      return;
    }
    const key = `${start_local}|${end_local}|${duration_minutes}`;
    if (!dedupe.has(key)) {
      dedupe.set(key, { start_local, end_local, duration_minutes });
    }
  });
  const unique = [...dedupe.values()].sort((a, b) => a.start_local.localeCompare(b.start_local));
  return dropSlotsContainedInAnother(unique);
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

export function formatLocalTime12h(hhmm) {
  const raw = String(hhmm || "").trim();
  const [hhRaw, mmRaw] = raw.split(":");
  const hh = Number(hhRaw);
  const mm = Number(mmRaw);
  if (!Number.isFinite(hh) || !Number.isFinite(mm)) return raw;
  const period = hh >= 12 ? "PM" : "AM";
  const hour12 = hh % 12 === 0 ? 12 : hh % 12;
  return `${hour12}:${String(mm).padStart(2, "0")} ${period}`;
}

export function formatSlotLabel(slot) {
  const end = slot.end_local || "";
  const duration = slot.duration_minutes ?? slotDurationMinutes(slot.start_local, end);
  return `${formatLocalTime12h(slot.start_local)} – ${formatLocalTime12h(end)} (${duration} min)`;
}

export function normalizeAvailableSlots(sourceData) {
  const publishedRaw = Array.isArray(sourceData?.published_slots) ? sourceData.published_slots : [];
  const published = publishedRaw.map((s) => ({
    start_local: String(s.start_local || ""),
    end_local: String(s.end_local || ""),
    duration_minutes: Number(s.duration_minutes) || slotDurationMinutes(s.start_local, s.end_local),
  }));
  const explicit = Array.isArray(sourceData?.available_slots) ? sourceData.available_slots : [];
  if (explicit.length > 0) {
    const mapped = explicit.map((s) => ({
      start_local: String(s.start_local || ""),
      end_local: String(s.end_local || ""),
      duration_minutes: Number(s.duration_minutes) || slotDurationMinutes(s.start_local, s.end_local),
    }));
    return filterSlotsToPublishedOnly(mapped, published);
  }
  if (published.length > 0) {
    return dedupeSlots(published);
  }
  return [];
}

export function buildSlotsFromFranjas(franjas) {
  const mapped = (franjas || []).map((window) => {
    const start_local = String(window.start_local || "");
    const end_local = String(window.end_local || "");
    const duration_minutes =
      Number(window.duration_minutes) || slotDurationMinutes(start_local, end_local);
    return { start_local, end_local, duration_minutes };
  });
  return dedupeSlots(mapped);
}
