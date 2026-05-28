import { useState } from "react";

const field =
  "w-full rounded-lg border border-slate-400 bg-white px-3 py-2 text-sm text-slate-900 focus:border-[#35783C] focus:outline-none focus:ring-2 focus:ring-[#35783C]/30";

/**
 * Confirmación para cambios de cita que no coinciden con un turno estándar (requiere motivo).
 */
export default function StaffAppointmentChangeConfirm({
  open,
  title = "Confirmar cambio de cita",
  warningMessage,
  currentSummary,
  proposedSummary,
  onConfirm,
  onCancel,
  overlayZIndexClass = "z-[110]",
}) {
  const [reason, setReason] = useState("");
  const [localError, setLocalError] = useState("");

  if (!open) return null;

  const handleConfirm = () => {
    const trimmed = reason.trim();
    if (trimmed.length < 10) {
      setLocalError("Escribe al menos 10 caracteres explicando por qué confirmas el cambio.");
      return;
    }
    setLocalError("");
    onConfirm(trimmed);
  };

  const handleCancel = () => {
    setReason("");
    setLocalError("");
    onCancel();
  };

  return (
    <div
      className={`fixed inset-0 ${overlayZIndexClass} flex items-center justify-center bg-black/50 p-4`}
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="staff-change-confirm-title"
    >
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-xl border border-slate-200 bg-white p-6 shadow-xl">
        <h3 id="staff-change-confirm-title" className="text-lg font-semibold text-slate-900">
          {title}
        </h3>
        <p className="mt-2 text-sm text-amber-800">{warningMessage}</p>
        {currentSummary ? (
          <p className="mt-3 text-xs text-slate-600">
            <span className="font-semibold text-slate-800">Horario actual:</span> {currentSummary}
          </p>
        ) : null}
        {proposedSummary ? (
          <p className="mt-1 text-xs text-slate-600">
            <span className="font-semibold text-slate-800">Horario propuesto:</span> {proposedSummary}
          </p>
        ) : null}
        <div className="mt-4">
          <label htmlFor="staff-change-reason" className="mb-1 block text-xs font-medium text-slate-700">
            ¿Por qué estás seguro de aplicar este cambio?
          </label>
          <textarea
            id="staff-change-reason"
            className={field}
            rows={4}
            placeholder="Ej.: Las citas tienen horarios distintos pero deben quedar consecutivas (termina 2:00 y la siguiente empieza 2:00)."
            value={reason}
            onChange={(e) => {
              setReason(e.target.value);
              if (localError) setLocalError("");
            }}
          />
          {localError ? <p className="mt-1 text-xs text-rose-700">{localError}</p> : null}
        </div>
        <div className="mt-6 flex flex-wrap justify-end gap-2">
          <button
            type="button"
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50"
            onClick={handleCancel}
          >
            No, volver
          </button>
          <button
            type="button"
            className="rounded-lg bg-[#35783C] px-4 py-2 text-sm font-medium text-white hover:bg-[#2d6532]"
            onClick={handleConfirm}
          >
            Sí, confirmar cambio
          </button>
        </div>
      </div>
    </div>
  );
}
