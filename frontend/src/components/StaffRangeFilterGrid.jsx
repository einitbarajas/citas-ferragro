import MonthYearSelects from "./MonthYearSelects";
import { getPeriodSelectorLabel, rangeNeedsPeriodSelector } from "../utils/reportRange";

/**
 * Filtros de rango (día / semana / quincena / mes) + bodega, mismo diseño en Citas y Revisión.
 */
export default function StaffRangeFilterGrid({
  inputClass,
  rangeId,
  rangeLabel,
  range,
  onRangeChange,
  dayId,
  day,
  onDayChange,
  periodId,
  period,
  onPeriodChange,
  periodOptions = [],
  month,
  year,
  onMonthChange,
  onYearChange,
  monthId,
  yearId,
  warehouseId,
  warehouseSelectId,
  warehouses = [],
  onWarehouseChange,
  labelClassName = "mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500",
  porLabels = false,
}) {
  const rangeOptions = porLabels
    ? [
        { value: "today", label: "Por día" },
        { value: "week", label: "Por semana" },
        { value: "biweekly", label: "Por quincena" },
        { value: "month", label: "Por mes" },
      ]
    : [
        { value: "today", label: "Día" },
        { value: "week", label: "Semana" },
        { value: "biweekly", label: "Quincena" },
        { value: "month", label: "Mes" },
      ];

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <div>
        <label htmlFor={rangeId} className={labelClassName}>
          {rangeLabel}
        </label>
        <select id={rangeId} name={rangeId} className={inputClass} value={range} onChange={onRangeChange}>
          {rangeOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>
      {range === "today" && (
        <div>
          <label htmlFor={dayId} className={labelClassName}>
            Día
          </label>
          <input id={dayId} name={dayId} type="date" className={inputClass} value={day} onChange={onDayChange} />
        </div>
      )}
      {rangeNeedsPeriodSelector(range) && periodOptions.length > 0 && (
        <div>
          <label htmlFor={periodId} className={labelClassName}>
            {getPeriodSelectorLabel(range)}
          </label>
          <select id={periodId} name={periodId} className={inputClass} value={period ?? 1} onChange={onPeriodChange}>
            {periodOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      )}
      {range === "month" && (
        <MonthYearSelects
          month={month}
          year={year}
          onMonthChange={onMonthChange}
          onYearChange={onYearChange}
          inputClass={inputClass}
          monthId={monthId}
          yearId={yearId}
          labelClassName={labelClassName}
        />
      )}
      <div>
        <label htmlFor={warehouseSelectId} className={labelClassName}>
          Bodega
        </label>
        <select
          id={warehouseSelectId}
          className={inputClass}
          value={warehouseId}
          onChange={(e) => onWarehouseChange(e.target.value)}
        >
          <option value="">Todas las bodegas</option>
          {warehouses.map((w) => (
            <option key={w.id} value={String(w.id)}>
              {w.name}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
