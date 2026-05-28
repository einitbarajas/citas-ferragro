function monthEndDate(year, month) {
  return new Date(year, month + 1, 1);
}

export const MONTH_OPTIONS = [
  { value: 1, label: "Enero" },
  { value: 2, label: "Febrero" },
  { value: 3, label: "Marzo" },
  { value: 4, label: "Abril" },
  { value: 5, label: "Mayo" },
  { value: 6, label: "Junio" },
  { value: 7, label: "Julio" },
  { value: 8, label: "Agosto" },
  { value: 9, label: "Septiembre" },
  { value: 10, label: "Octubre" },
  { value: 11, label: "Noviembre" },
  { value: 12, label: "Diciembre" },
];

export function listYearOptions(yearsBefore = 3, yearsAfter = 3) {
  const current = new Date().getFullYear();
  const years = [];
  for (let y = current - yearsBefore; y <= current + yearsAfter; y += 1) {
    years.push(y);
  }
  return years;
}

export function referenceDateForMonthYear(month, year) {
  return new Date(Number(year), Number(month) - 1, 15, 12, 0, 0);
}

export function listMonthWeekBounds(referenceDate = new Date()) {
  const ref = new Date(referenceDate);
  const year = ref.getFullYear();
  const month = ref.getMonth();
  const monthStart = new Date(year, month, 1);
  const monthEnd = monthEndDate(year, month);
  const weeks = [];
  const monday = new Date(monthStart);
  monday.setDate(monthStart.getDate() - ((monthStart.getDay() + 6) % 7));

  while (monday < monthEnd) {
    const weekEnd = new Date(monday);
    weekEnd.setDate(monday.getDate() + 7);
    if (weekEnd > monthStart && monday < monthEnd) {
      weeks.push({ start: new Date(monday), end: new Date(weekEnd) });
    }
    monday.setDate(monday.getDate() + 7);
  }
  return weeks;
}

export function getDefaultPeriodIndex(range, referenceDate = new Date()) {
  const ref = new Date(referenceDate);
  if (range === "biweekly") return ref.getDate() <= 15 ? 1 : 2;
  if (range === "week") {
    const weeks = listMonthWeekBounds(ref);
    const today = new Date(ref.getFullYear(), ref.getMonth(), ref.getDate());
    const index = weeks.findIndex((w) => today >= w.start && today < w.end);
    return index >= 0 ? index + 1 : 1;
  }
  return null;
}

export function formatInclusiveDayRange(start, endExclusive) {
  const endInclusive = new Date(endExclusive);
  endInclusive.setDate(endInclusive.getDate() - 1);
  const sameMonth = start.getMonth() === endInclusive.getMonth();
  const startText = start.toLocaleDateString("es-CO", { day: "numeric", month: "short" });
  const endText = sameMonth
    ? endInclusive.toLocaleDateString("es-CO", { day: "numeric" })
    : endInclusive.toLocaleDateString("es-CO", { day: "numeric", month: "short" });
  return `${startText} al ${endText}`;
}

export function getPeriodSelectorLabel(range) {
  if (range === "biweekly") return "Quincena";
  if (range === "week") return "Semana del mes";
  return "";
}

export function getAnalyticsPeriodOptions(range, referenceDate = new Date()) {
  if (range === "biweekly") {
    return [1, 2].map((value) => {
      const { start, end } = getReportRangeBounds("biweekly", referenceDate, value);
      return {
        value,
        label: `${value}.ª quincena (${formatInclusiveDayRange(start, end)})`,
      };
    });
  }
  if (range === "week") {
    const weeks = listMonthWeekBounds(referenceDate);
    return weeks.map((w, i) => ({
      value: i + 1,
      label: `Semana ${i + 1} (${formatInclusiveDayRange(w.start, w.end)})`,
    }));
  }
  return [];
}

export function rangeNeedsPeriodSelector(range) {
  return range === "week" || range === "biweekly";
}

export function getReportRangeBounds(range, referenceDate = new Date(), period = null) {
  const ref = new Date(referenceDate);
  const today = new Date(ref.getFullYear(), ref.getMonth(), ref.getDate());
  const year = today.getFullYear();
  const month = today.getMonth();

  if (range === "month") {
    return {
      start: new Date(year, month, 1),
      end: monthEndDate(year, month),
    };
  }

  if (range === "week") {
    if (period != null) {
      const weeks = listMonthWeekBounds(ref);
      const index = Math.max(1, Math.min(Number(period), weeks.length)) - 1;
      if (weeks[index]) return weeks[index];
    }
    const mondayOffset = (today.getDay() + 6) % 7;
    const start = new Date(today);
    start.setDate(today.getDate() - mondayOffset);
    const end = new Date(start);
    end.setDate(start.getDate() + 7);
    return { start, end };
  }

  if (range === "biweekly") {
    if (period === 1) {
      return {
        start: new Date(year, month, 1),
        end: new Date(year, month, 16),
      };
    }
    if (period === 2) {
      return {
        start: new Date(year, month, 16),
        end: monthEndDate(year, month),
      };
    }
    if (today.getDate() <= 15) {
      return {
        start: new Date(year, month, 1),
        end: new Date(year, month, 16),
      };
    }
    return {
      start: new Date(year, month, 16),
      end: monthEndDate(year, month),
    };
  }

  const end = new Date(today);
  end.setDate(end.getDate() + 1);
  return { start: today, end };
}

export function formatReportRangeLabel(range, referenceDate = new Date(), period = null) {
  const { start, end } = getReportRangeBounds(range, referenceDate, period);
  const monthLabel = start.toLocaleDateString("es-CO", { month: "long", year: "numeric" });

  if (range === "today") {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const isActualToday =
      start.getFullYear() === today.getFullYear() &&
      start.getMonth() === today.getMonth() &&
      start.getDate() === today.getDate();
    if (isActualToday) return "día actual";
    return `día ${start.toLocaleDateString("es-CO", { day: "numeric", month: "short", year: "numeric" })}`;
  }
  if (range === "month") {
    const endInclusive = new Date(end);
    endInclusive.setDate(endInclusive.getDate() - 1);
    return `${monthLabel} (${start.getDate()} al ${endInclusive.getDate()})`;
  }
  if (range === "week") {
    const endInclusive = new Date(end);
    endInclusive.setDate(endInclusive.getDate() - 1);
    const sameMonth = start.getMonth() === endInclusive.getMonth();
    const endText = sameMonth
      ? endInclusive.toLocaleDateString("es-CO", { day: "numeric" })
      : endInclusive.toLocaleDateString("es-CO", { day: "numeric", month: "short" });
    const weekPrefix = period != null ? `semana ${period} (` : "semana del ";
    const weekSuffix = period != null ? ")" : "";
    return `${weekPrefix}${start.toLocaleDateString("es-CO", { day: "numeric", month: "short" })} al ${endText}${weekSuffix}`;
  }
  if (range === "biweekly") {
    const quincena = period === 1 || (period == null && start.getDate() === 1) ? "1.ª" : "2.ª";
    const endInclusive = new Date(end);
    endInclusive.setDate(endInclusive.getDate() - 1);
    const fromDay = start.toLocaleDateString("es-CO", { day: "numeric" });
    const toDay = endInclusive.toLocaleDateString("es-CO", { day: "numeric", month: "long", year: "numeric" });
    return `${quincena} quincena (${fromDay} al ${toDay})`;
  }
  return "rango seleccionado";
}
