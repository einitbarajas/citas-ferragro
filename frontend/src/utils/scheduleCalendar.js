import { todayISOInTimeZone, DEFAULT_BUSINESS_TZ } from "./businessTime";

/** Normaliza respuesta de /appointment-franjas/fecha/resumen para admin y proveedor. */
export function parseFranjaMonthSummary(payload) {
  const data = payload?.data && typeof payload.data === "object" ? payload.data : {};
  const tz = String(data.timezone || DEFAULT_BUSINESS_TZ);
  const businessToday = String(data.business_today || todayISOInTimeZone(tz));
  const openDays = (Array.isArray(data.open_days) ? data.open_days : [])
    .map(String)
    .filter((d) => d >= businessToday);
  const overrideDays = (Array.isArray(data.override_days) ? data.override_days : []).map(String);
  return {
    timezone: tz,
    businessToday,
    openDays,
    overrideDays,
    hasWeeklyFranjas: Boolean(data.has_weekly_franjas),
    scheduledIsoWeekdays: Array.isArray(data.scheduled_iso_weekdays)
      ? data.scheduled_iso_weekdays.map(Number)
      : [],
  };
}

export function buildMonthCalendarCells(referenceDate, businessToday) {
  const today = String(businessToday || todayISOInTimeZone());
  const year = referenceDate.getFullYear();
  const month = referenceDate.getMonth();
  const first = new Date(year, month, 1);
  const last = new Date(year, month + 1, 0);
  const getIsoWeekday = (date) => {
    const js = date.getDay();
    return js === 0 ? 7 : js;
  };
  const leading = getIsoWeekday(first) - 1;
  const cells = [];
  for (let i = 0; i < leading; i += 1) {
    cells.push(null);
  }
  for (let day = 1; day <= last.getDate(); day += 1) {
    const d = new Date(year, month, day);
    const dateISO = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    const isoWeekday = getIsoWeekday(d);
    cells.push({
      day,
      dateISO,
      isoWeekday,
      isToday: dateISO === today,
      isPast: dateISO < today,
    });
  }
  return { year, month, cells };
}
