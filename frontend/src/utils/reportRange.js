export function getReportRangeBounds(range, referenceDate = new Date()) {
  const ref = new Date(referenceDate);
  const today = new Date(ref.getFullYear(), ref.getMonth(), ref.getDate());

  if (range === "month") {
    return {
      start: new Date(today.getFullYear(), today.getMonth(), 1),
      end: new Date(today.getFullYear(), today.getMonth() + 1, 1),
    };
  }

  if (range === "week") {
    const mondayOffset = (today.getDay() + 6) % 7;
    const start = new Date(today);
    start.setDate(today.getDate() - mondayOffset);
    const end = new Date(start);
    end.setDate(start.getDate() + 7);
    return { start, end };
  }

  if (range === "biweekly") {
    if (today.getDate() <= 15) {
      return {
        start: new Date(today.getFullYear(), today.getMonth(), 1),
        end: new Date(today.getFullYear(), today.getMonth(), 16),
      };
    }
    return {
      start: new Date(today.getFullYear(), today.getMonth(), 16),
      end: new Date(today.getFullYear(), today.getMonth() + 1, 1),
    };
  }

  const end = new Date(today);
  end.setDate(end.getDate() + 1);
  return { start: today, end };
}

export function formatReportRangeLabel(range, referenceDate = new Date()) {
  const { start, end } = getReportRangeBounds(range, referenceDate);
  const monthLabel = start.toLocaleDateString("es-CO", { month: "long", year: "numeric" });

  if (range === "today") return "día actual";
  if (range === "month") return monthLabel;
  if (range === "week") {
    const endInclusive = new Date(end);
    endInclusive.setDate(endInclusive.getDate() - 1);
    const sameMonth = start.getMonth() === endInclusive.getMonth();
    const endText = sameMonth
      ? endInclusive.toLocaleDateString("es-CO", { day: "numeric" })
      : endInclusive.toLocaleDateString("es-CO", { day: "numeric", month: "short" });
    return `semana del ${start.toLocaleDateString("es-CO", { day: "numeric", month: "short" })} al ${endText}`;
  }
  if (range === "biweekly") {
    return start.getDate() === 1 ? `1.ª quincena de ${monthLabel}` : `2.ª quincena de ${monthLabel}`;
  }
  return "rango seleccionado";
}
