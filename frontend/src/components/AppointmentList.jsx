import { useMemo, useState } from "react";
import ConfirmDialog from "./ConfirmDialog";
import AppointmentReschedulePanel from "./AppointmentReschedulePanel";

const field =
  "rounded-lg border border-slate-400 bg-white px-2 py-1.5 text-sm text-[#121212] focus:border-[#35783C] focus:outline-none focus:ring-2 focus:ring-[#35783C]/30";
const actionButtonClass =
  "min-h-11 w-full rounded-lg px-2.5 py-1.5 text-xs font-medium transition sm:w-auto focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#35783C]/40 disabled:opacity-40";

export default function AppointmentList({
  appointments,
  role,
  onReview,
  onChangeStatus,
  onExtend,
  onReschedule,
  title = "Citas",
  reviewMode = false,
  viewMode,
  onViewModeChange,
  filterDay,
  onFilterDayChange,
  filterMonth,
  onFilterMonthChange,
  filterYear,
  onFilterYearChange,
  emptyMessage = "No hay citas para este filtro.",
}) {
  const showStaffActions = role === "Logistica" || role === "Admin";
  const [companyFilter, setCompanyFilter] = useState("");
  const [nitFilter, setNitFilter] = useState("");
  const [confirmCancelId, setConfirmCancelId] = useState(null);
  const [editAppointment, setEditAppointment] = useState(null);

  const filteredAppointments = useMemo(() => {
    const companyNeedle = companyFilter.trim().toLowerCase();
    const nitNeedle = nitFilter.replace(/\D/g, "");
    return appointments.filter((a) => {
      const providerName = String(a.provider_name || "").toLowerCase();
      const providerNit = String(a.provider_id || "").replace(/\D/g, "");
      if (companyNeedle && !providerName.includes(companyNeedle)) return false;
      if (nitNeedle && !providerNit.includes(nitNeedle)) return false;
      return true;
    });
  }, [appointments, companyFilter, nitFilter]);

  const statusLabel = (status) => {
    if (status === "sin_revision") return "Sin revision";
    if (status === "revisado") return "Revisada";
    if (status === "finalizada") return "Finalizada";
    if (status === "no_presentada") return "No presentada";
    if (status === "cancelado") return "Cancelada";
    return status;
  };
  const statusMeta = (status) => {
    if (status === "sin_revision") return { icon: "🕒", label: "Sin revisión", className: "text-amber-700" };
    if (status === "revisado") return { icon: "✓", label: "Revisada", className: "text-[#35783C]" };
    if (status === "finalizada") return { icon: "✔", label: "Finalizada", className: "text-[#008000]" };
    if (status === "no_presentada") return { icon: "⚠", label: "No presentada", className: "text-slate-700" };
    if (status === "cancelado") return { icon: "✕", label: "Cancelada", className: "text-rose-700" };
    return { icon: "•", label: statusLabel(status), className: "text-slate-700" };
  };

  const isLogisticaClosed = (appointment) =>
    role === "Logistica" &&
    (appointment.status === "cancelado" ||
      appointment.status === "finalizada" ||
      appointment.status === "no_presentada");

  const canManageAppointment = (appointment) =>
    showStaffActions && !isLogisticaClosed(appointment);

  const canRescheduleAppointment = (appointment) =>
    appointment.status === "sin_revision" || appointment.status === "revisado";

  const renderStaffActions = (appointment) => {
    if (!canManageAppointment(appointment)) return null;
    const a = appointment;
    return (
      <div className="mt-4 flex flex-wrap gap-2">
        {!(role === "Logistica" && a.status === "revisado") && (
          <>
            {role === "Admin" && (
              <button
                className={`${actionButtonClass} border border-sky-300 bg-sky-50 text-sky-900 hover:bg-sky-100`}
                disabled={a.status === "sin_revision"}
                onClick={() => onChangeStatus?.(a.id, "sin_revision")}
                aria-label={`Marcar como sin revisión la cita #${a.id} de ${a.provider_name || "proveedor sin nombre"}`}
              >
                Marcar sin revisión
              </button>
            )}
            <button
              className={`${actionButtonClass} bg-[#35783C] text-white hover:bg-[#2d6532]`}
              disabled={a.status === "revisado"}
              onClick={() => onReview(a.id)}
              aria-label={`Marcar como revisada la cita #${a.id} de ${a.provider_name || "proveedor sin nombre"}`}
            >
              Marcar revisado
            </button>
            <button
              className={`${actionButtonClass} border border-[#35783C] bg-emerald-50 text-[#121212] hover:bg-emerald-100`}
              disabled={a.status === "finalizada"}
              onClick={() => onChangeStatus?.(a.id, "finalizada")}
              aria-label={`Marcar como finalizada la cita #${a.id} de ${a.provider_name || "proveedor sin nombre"}`}
            >
              Marcar finalizada
            </button>
            <button
              className={`${actionButtonClass} border border-slate-300 bg-slate-100 text-slate-900 hover:bg-slate-200`}
              disabled={a.status === "no_presentada"}
              onClick={() => onChangeStatus?.(a.id, "no_presentada")}
              aria-label={`Marcar como no presentada la cita #${a.id} de ${a.provider_name || "proveedor sin nombre"}`}
            >
              Marcar no presentada
            </button>
            {role === "Admin" && (
              <button
                className={`${actionButtonClass} border border-rose-300 bg-rose-50 text-rose-900 hover:bg-rose-100`}
                disabled={a.status === "cancelado"}
                title="Cancelar la cita (administrador sin limite de anticipacion)"
                onClick={() => setConfirmCancelId(a.id)}
                aria-label={`Cancelar la cita #${a.id} de ${a.provider_name || "proveedor sin nombre"}`}
              >
                Cancelar cita
              </button>
            )}
          </>
        )}
        {role === "Logistica" && a.status === "revisado" && (
          <>
            <button
              className={`${actionButtonClass} border border-[#35783C] bg-emerald-50 text-[#121212] hover:bg-emerald-100`}
              onClick={() => onChangeStatus?.(a.id, "finalizada")}
              aria-label={`Confirmar finalizada la cita #${a.id} de ${a.provider_name || "proveedor sin nombre"}`}
            >
              Confirmar finalizada
            </button>
            <button
              className={`${actionButtonClass} border border-slate-300 bg-slate-100 text-slate-900 hover:bg-slate-200`}
              onClick={() => onChangeStatus?.(a.id, "no_presentada")}
              aria-label={`Confirmar no presentada la cita #${a.id} de ${a.provider_name || "proveedor sin nombre"}`}
            >
              Confirmar no presentada
            </button>
          </>
        )}
        {!reviewMode && !(role === "Logistica" && a.status === "revisado") && (
          <button
            className={`${actionButtonClass} border border-amber-300 bg-amber-50 text-amber-900 hover:bg-amber-100`}
            onClick={() => onExtend(a.id, 30)}
            title="Extiende 30 min si no hay otra cita pegada después"
            aria-label={`Extender 30 minutos la cita #${a.id} de ${a.provider_name || "proveedor sin nombre"}`}
          >
            Extender +30 min
          </button>
        )}
        {reviewMode && !(role === "Logistica" && a.status === "revisado") && (
          <>
            <button
              className={`${actionButtonClass} border border-amber-300 bg-amber-50 text-amber-900 hover:bg-amber-100`}
              onClick={() => onExtend(a.id, 30)}
              aria-label={`Extender 30 minutos la cita #${a.id} de ${a.provider_name || "proveedor sin nombre"}`}
            >
              +30 min
            </button>
            <button
              className={`${actionButtonClass} border border-amber-300 bg-amber-50 text-amber-900 hover:bg-amber-100`}
              onClick={() => onExtend(a.id, 60)}
              aria-label={`Extender 60 minutos la cita #${a.id} de ${a.provider_name || "proveedor sin nombre"}`}
            >
              +60 min
            </button>
            <button
              className={`${actionButtonClass} border border-amber-300 bg-amber-50 text-amber-900 hover:bg-amber-100`}
              onClick={() => onExtend(a.id, 90)}
              aria-label={`Extender 90 minutos la cita #${a.id} de ${a.provider_name || "proveedor sin nombre"}`}
            >
              +90 min
            </button>
          </>
        )}
      </div>
    );
  };

  const renderAppointmentDetails = (appointment) => (
    <>
      <p className="text-sm text-slate-600">{appointment.material_description}</p>
      <p className="mt-2 text-sm text-slate-700">
        Proveedor: <span className="font-medium">{appointment.provider_name || "—"}</span> (NIT {appointment.provider_id})
      </p>
      <p className="text-sm text-slate-700">Inicio: {new Date(appointment.start_time).toLocaleString()}</p>
      <p className="text-sm text-slate-700">Duración: {appointment.duration_minutes} min</p>
      <p className={`text-sm ${statusMeta(appointment.status).className}`}>
        Estado: {`${statusMeta(appointment.status).icon} ${statusMeta(appointment.status).label}`}
      </p>
    </>
  );

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
      <ConfirmDialog
        open={confirmCancelId !== null}
        title="Cancelar cita"
        danger
        confirmLabel="Sí, cancelar"
        onCancel={() => setConfirmCancelId(null)}
        onConfirm={() => {
          if (confirmCancelId !== null) onChangeStatus?.(confirmCancelId, "cancelado");
          setConfirmCancelId(null);
        }}
      >
        ¿Seguro que deseas cancelar esta cita? Solo se permite con al menos 24 horas de anticipación (validado en el servidor).
      </ConfirmDialog>
      <h2 className="mb-3 text-lg font-semibold text-slate-900">{title}</h2>

      {(role === "Logistica" || role === "Admin") && !reviewMode && (
        <div className="mb-4 grid gap-3 border-b border-slate-100 pb-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="sm:col-span-1">
            <label className="mb-1 block text-xs font-medium text-slate-600">Vista</label>
            <select className={field} value={viewMode} onChange={(e) => onViewModeChange(e.target.value)}>
              <option value="list">Lista (todas)</option>
              <option value="day">Por día</option>
              <option value="week">Por semana</option>
              <option value="biweekly">Por quincena</option>
              <option value="month">Por mes</option>
            </select>
          </div>
          {viewMode === "day" && (
            <div className="sm:col-span-1">
              <label className="mb-1 block text-xs font-medium text-slate-600">Día</label>
              <input type="date" className={field + " w-full"} value={filterDay} onChange={(e) => onFilterDayChange(e.target.value)} />
            </div>
          )}
          {viewMode === "month" && (
            <>
              <div className="sm:col-span-1">
                <label className="mb-1 block text-xs font-medium text-slate-600">Mes</label>
                <select className={field} value={filterMonth} onChange={(e) => onFilterMonthChange(Number(e.target.value))}>
                  {Array.from({ length: 12 }, (_, i) => (
                    <option key={i + 1} value={i + 1}>
                      {new Date(2000, i, 1).toLocaleString("es", { month: "long" })}
                    </option>
                  ))}
                </select>
              </div>
              <div className="sm:col-span-1">
                <label className="mb-1 block text-xs font-medium text-slate-600">Año</label>
                <input
                  type="number"
                  min={2000}
                  max={2100}
                  className={field + " w-full"}
                  value={filterYear}
                  onChange={(e) => onFilterYearChange(Number(e.target.value))}
                />
              </div>
            </>
          )}
          <div className="sm:col-span-1">
            <label className="mb-1 block text-xs font-medium text-slate-600">Empresa</label>
            <input
              type="text"
              className={field + " w-full"}
              placeholder="Nombre de empresa"
              value={companyFilter}
              onChange={(e) => setCompanyFilter(e.target.value)}
            />
          </div>
          <div className="sm:col-span-1">
            <label className="mb-1 block text-xs font-medium text-slate-600">NIT</label>
            <input
              type="text"
              inputMode="numeric"
              className={field + " w-full"}
              placeholder="NIT empresa"
              value={nitFilter}
              maxLength={10}
              pattern="^\d{10}$"
              title="El NIT debe tener exactamente 10 dígitos"
              onChange={(e) => setNitFilter(e.target.value.replace(/\D/g, "").slice(0, 10))}
            />
          </div>
        </div>
      )}

      <div className="space-y-3">
        {filteredAppointments.length === 0 && <p className="text-sm text-slate-500">{emptyMessage}</p>}
        {filteredAppointments.map((a) => (
          <div key={a.id} className="rounded-lg border border-slate-100 bg-slate-50/80 p-3">
            {showStaffActions ? (
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-slate-900">Cita #{a.id}</p>
                  <p className="truncate text-sm text-slate-600">{a.provider_name || "—"}</p>
                  <p className="text-sm text-slate-700">{new Date(a.start_time).toLocaleString()}</p>
                  <p className={`text-sm ${statusMeta(a.status).className}`}>
                    {`${statusMeta(a.status).icon} ${statusMeta(a.status).label}`}
                  </p>
                </div>
                <button
                  type="button"
                  className={`${actionButtonClass} shrink-0 border border-[#35783C] bg-white text-[#35783C] hover:bg-emerald-50`}
                  onClick={() => setEditAppointment(a)}
                  aria-label={`${canManageAppointment(a) ? "Editar" : "Ver"} la cita #${a.id} de ${a.provider_name || "proveedor sin nombre"}`}
                >
                  {canManageAppointment(a) ? "Editar cita" : "Ver cita"}
                </button>
              </div>
            ) : (
              <>
                <p className="font-medium text-slate-900">Cita #{a.id}</p>
                {renderAppointmentDetails(a)}
              </>
            )}
          </div>
        ))}
      </div>

      {editAppointment && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/45 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="appointment-dialog-title"
          onClick={() => setEditAppointment(null)}
        >
          <div
            className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-xl border border-slate-200 bg-white p-6 shadow-xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3">
              <h3 id="appointment-dialog-title" className="text-lg font-semibold text-slate-900">
                Cita #{editAppointment.id}
              </h3>
              <button
                type="button"
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                onClick={() => setEditAppointment(null)}
              >
                Cerrar
              </button>
            </div>
            {isLogisticaClosed(editAppointment) && (
              <p className="mt-3 text-xs font-medium text-amber-700">
                Esta cita ya está cerrada. Solo se muestra el estado.
              </p>
            )}
            <div className="mt-3">{renderAppointmentDetails(editAppointment)}</div>
            {canManageAppointment(editAppointment) && canRescheduleAppointment(editAppointment) && onReschedule && (
              <AppointmentReschedulePanel
                appointment={editAppointment}
                variant="staff"
                inputClass={field}
                buttonClass={`${actionButtonClass} bg-[#35783C] text-white hover:bg-[#2d6532]`}
                onReschedule={async (payload) => {
                  await onReschedule(payload);
                  setEditAppointment(null);
                }}
              />
            )}
            {renderStaffActions(editAppointment)}
          </div>
        </div>
      )}
    </div>
  );
}
