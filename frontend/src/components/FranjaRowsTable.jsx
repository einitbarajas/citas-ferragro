import { slotDurationMinutes } from "../utils/appointmentSlots";

function normalizeTimeValue(value) {
  const raw = String(value || "");
  return raw.length >= 5 ? raw.slice(0, 5) : raw;
}

function durationLabel(startLocal, endLocal) {
  if (!startLocal || !endLocal || endLocal <= startLocal) return "—";
  const minutes = slotDurationMinutes(startLocal, endLocal);
  if (minutes < 15) return `${minutes} min (mín. 15)`;
  return `${minutes} min`;
}

export default function FranjaRowsTable({
  rows,
  inputClass,
  disabled = false,
  idPrefix = "franja",
  onChangeRow,
  onRemoveRow,
  emptyMessage = "No hay franjas definidas.",
}) {
  if (!rows.length) {
    return <p className="rounded-lg border border-dashed border-slate-200 bg-white px-3 py-4 text-sm text-slate-500">{emptyMessage}</p>;
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="w-full min-w-[28rem] border-collapse text-sm">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50">
            <th
              scope="col"
              className="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-600"
            >
              Inicio
            </th>
            <th
              scope="col"
              className="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-600"
            >
              Fin
            </th>
            <th
              scope="col"
              className="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-600"
            >
              Duración
            </th>
            <th
              scope="col"
              className="w-28 px-3 py-2.5 text-right text-xs font-semibold uppercase tracking-wide text-slate-600"
            >
              Acción
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr
              key={`${idPrefix}-row-${idx}`}
              className="border-b border-slate-100 last:border-b-0 odd:bg-white even:bg-slate-50/50"
            >
              <td className="px-3 py-2 align-middle">
                <input
                  id={`${idPrefix}-start-${idx}`}
                  type="time"
                  className={inputClass}
                  value={normalizeTimeValue(row.start_local)}
                  disabled={disabled}
                  onChange={(e) => onChangeRow(idx, "start_local", e.target.value)}
                  required
                  aria-label={`Hora inicio franja ${idx + 1}`}
                />
              </td>
              <td className="px-3 py-2 align-middle">
                <input
                  id={`${idPrefix}-end-${idx}`}
                  type="time"
                  className={inputClass}
                  value={normalizeTimeValue(row.end_local)}
                  disabled={disabled}
                  onChange={(e) => onChangeRow(idx, "end_local", e.target.value)}
                  required
                  aria-label={`Hora fin franja ${idx + 1}`}
                />
              </td>
              <td className="px-3 py-2 align-middle text-slate-700 tabular-nums">
                {durationLabel(row.start_local, row.end_local)}
              </td>
              <td className="px-3 py-2 align-middle text-right">
                <button
                  type="button"
                  className="text-xs font-medium text-red-600 underline hover:text-red-700 disabled:cursor-not-allowed disabled:opacity-40"
                  disabled={disabled}
                  onClick={() => onRemoveRow(idx)}
                >
                  Quitar
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
