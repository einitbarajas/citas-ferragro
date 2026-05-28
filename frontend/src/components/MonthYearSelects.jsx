import { listYearOptions, MONTH_OPTIONS } from "../utils/reportRange";

export default function MonthYearSelects({
  month,
  year,
  onMonthChange,
  onYearChange,
  inputClass,
  monthId = "filter-month",
  yearId = "filter-year",
  monthLabel = "Mes",
  yearLabel = "Año",
  labelClassName = "mb-1 block text-xs font-medium text-slate-600",
  cellClassName = "",
}) {
  const years = listYearOptions();

  return (
    <>
      <div className={cellClassName}>
        <label htmlFor={monthId} className={labelClassName}>
          {monthLabel}
        </label>
        <select
          id={monthId}
          name={monthId}
          className={inputClass}
          value={month}
          onChange={(e) => onMonthChange(Number(e.target.value))}
        >
          {MONTH_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>
      <div className={cellClassName}>
        <label htmlFor={yearId} className={labelClassName}>
          {yearLabel}
        </label>
        <select
          id={yearId}
          name={yearId}
          className={inputClass}
          value={year}
          onChange={(e) => onYearChange(Number(e.target.value))}
        >
          {years.map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
      </div>
    </>
  );
}
