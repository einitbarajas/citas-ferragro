import { lazy, Suspense, useEffect } from "react";
import { APPOINTMENT_CANCEL_MINIMUM_NOTICE_HOURS } from "../utils/businessTime";

const AppointmentReschedulePanel = lazy(() => import("./AppointmentReschedulePanel"));

function statusLabel(status) {
  if (status === "sin_revision") return "Sin revisión";
  if (status === "revisado") return "Revisada";
  if (status === "finalizada") return "Finalizada";
  if (status === "no_presentada") return "No presentada";
  if (status === "cancelado") return "Cancelada";
  return status || "—";
}

function canProviderManage(status) {
  return status !== "cancelado" && status !== "finalizada" && status !== "no_presentada";
}

function canProviderReschedule(status) {
  return status === "sin_revision" || status === "revisado";
}

export default function ProviderAppointmentNotificationModal({
  open,
  appointment,
  loading,
  error,
  cancelReason,
  onCancelReasonChange,
  rescheduleOpen,
  onToggleReschedule,
  onClose,
  onCancel,
  onReschedule,
  loadProviderDayAvailability,
  inputClass,
  buttonClass,
  rescheduleFallback,
}) {
  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (event) => {
      if (event.key === "Escape") onClose?.();
    };
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = prevOverflow;
    };
  }, [open, onClose]);

  if (!open) return null;

  const manageable = appointment ? canProviderManage(appointment.status) : false;
  const canReschedule = appointment ? canProviderReschedule(appointment.status) : false;

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-slate-900/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="provider-appointment-modal-title"
    >
      <button
        type="button"
        className="absolute inset-0 cursor-default"
        aria-label="Cerrar detalle de cita"
        onClick={onClose}
      />
      <div
        className="relative z-[201] w-full max-w-lg max-h-[min(90vh,40rem)] overflow-y-auto rounded-2xl border border-slate-200 bg-white shadow-2xl"
      >
        <div className="sticky top-0 z-10 flex items-start justify-between gap-3 border-b border-slate-100 bg-white px-5 py-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-emerald-800">Tu cita</p>
            <h2 id="provider-appointment-modal-title" className="mt-1 text-xl font-bold text-slate-900">
              {appointment ? `Cita #${appointment.id}` : "Detalle de cita"}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-200 px-2.5 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
            aria-label="Cerrar"
          >
            ✕
          </button>
        </div>

        <div className="px-5 py-4">
          {loading && <p className="text-sm text-slate-500">Cargando cita…</p>}
          {error && !loading && (
            <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800" role="alert">
              {error}
            </p>
          )}
          {appointment && !loading && (
            <div className="space-y-4">
              <dl className="grid gap-2 text-sm text-slate-700">
                <div>
                  <dt className="text-xs font-medium uppercase text-slate-500">Fecha y hora</dt>
                  <dd className="font-medium text-slate-900">
                    {new Date(appointment.start_time).toLocaleString("es-CO", {
                      weekday: "long",
                      day: "numeric",
                      month: "long",
                      year: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                      hour12: true,
                    })}
                  </dd>
                </div>
                {appointment.warehouse_name && (
                  <div>
                    <dt className="text-xs font-medium uppercase text-slate-500">Bodega</dt>
                    <dd>{appointment.warehouse_name}</dd>
                  </div>
                )}
                {appointment.warehouse_unload_team_name && (
                  <div>
                    <dt className="text-xs font-medium uppercase text-slate-500">Muelle</dt>
                    <dd>{appointment.warehouse_unload_team_name}</dd>
                  </div>
                )}
                <div>
                  <dt className="text-xs font-medium uppercase text-slate-500">Estado</dt>
                  <dd>{statusLabel(appointment.status)}</dd>
                </div>
                <div>
                  <dt className="text-xs font-medium uppercase text-slate-500">Duración</dt>
                  <dd>{appointment.duration_minutes || 60} minutos</dd>
                </div>
                <div>
                  <dt className="text-xs font-medium uppercase text-slate-500">Descripción</dt>
                  <dd className="whitespace-pre-wrap break-words">{appointment.material_description}</dd>
                </div>
              </dl>

              {!manageable && (
                <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
                  Esta cita ya no se puede modificar ni cancelar desde el panel.
                </p>
              )}

              {manageable && (
                <div className="space-y-3 border-t border-slate-100 pt-4">
                  {canReschedule && (
                    <button
                      type="button"
                      className="w-full rounded-lg border border-[#35783C] bg-white px-4 py-2.5 text-sm font-semibold text-[#35783C] hover:bg-emerald-50"
                      onClick={onToggleReschedule}
                    >
                      {rescheduleOpen ? "Ocultar cambio de fecha" : "Modificar fecha y hora"}
                    </button>
                  )}
                  {rescheduleOpen && canReschedule && (
                    <Suspense fallback={rescheduleFallback}>
                      <AppointmentReschedulePanel
                        appointment={appointment}
                        variant="provider"
                        inputClass={inputClass}
                        buttonClass={buttonClass}
                        loadProviderDayAvailability={loadProviderDayAvailability}
                        onReschedule={onReschedule}
                      />
                    </Suspense>
                  )}
                  <div className="space-y-2">
                    <label htmlFor="provider-modal-cancel-reason" className="block text-xs font-medium text-slate-600">
                      Motivo de cancelación (mín. 5 caracteres; anticipación mínima{" "}
                      {APPOINTMENT_CANCEL_MINIMUM_NOTICE_HOURS} horas)
                    </label>
                    <textarea
                      id="provider-modal-cancel-reason"
                      className={inputClass + " min-h-[72px] w-full"}
                      value={cancelReason}
                      onChange={(e) => onCancelReasonChange?.(e.target.value)}
                      placeholder="Indica por qué cancelas la cita"
                    />
                    <button
                      type="button"
                      className="w-full rounded-lg border border-rose-300 bg-rose-50 px-4 py-2.5 text-sm font-semibold text-rose-800 hover:bg-rose-100"
                      onClick={() => onCancel?.(appointment.id)}
                    >
                      Cancelar cita
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
