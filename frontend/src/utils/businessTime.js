export const DEFAULT_BUSINESS_TZ = "America/Bogota";

function readZonedParts(date, timeZone) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(date);
  const pick = (type) => Number(parts.find((part) => part.type === type)?.value || 0);
  return {
    year: pick("year"),
    month: pick("month"),
    day: pick("day"),
    hour: pick("hour"),
    minute: pick("minute"),
  };
}

export function formatDateInputInTimeZone(isoString, timeZone = DEFAULT_BUSINESS_TZ) {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return "";
  const parts = readZonedParts(date, timeZone);
  return `${parts.year}-${String(parts.month).padStart(2, "0")}-${String(parts.day).padStart(2, "0")}`;
}

export function formatTimeInputInTimeZone(isoString, timeZone = DEFAULT_BUSINESS_TZ) {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return "";
  const parts = readZonedParts(date, timeZone);
  return `${String(parts.hour).padStart(2, "0")}:${String(parts.minute).padStart(2, "0")}`;
}

export function buildDateTimeIsoInTimeZone(dateValue, timeValue, timeZone = DEFAULT_BUSINESS_TZ) {
  const [year, month, day] = dateValue.split("-").map(Number);
  const [hour, minute] = timeValue.split(":").map(Number);
  if (!year || !month || !day || Number.isNaN(hour) || Number.isNaN(minute)) return "";

  let utcMs = Date.UTC(year, month - 1, day, hour, minute, 0);
  for (let attempt = 0; attempt < 5; attempt += 1) {
    const zoned = readZonedParts(new Date(utcMs), timeZone);
    const desiredMs = Date.UTC(year, month - 1, day, hour, minute, 0);
    const actualMs = Date.UTC(zoned.year, zoned.month - 1, zoned.day, zoned.hour, zoned.minute, 0);
    const delta = desiredMs - actualMs;
    if (delta === 0) break;
    utcMs += delta;
  }
  return new Date(utcMs).toISOString();
}
