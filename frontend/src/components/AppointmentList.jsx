import { useCallback, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import ConfirmDialog from "./ConfirmDialog";
import AppointmentReschedulePanel from "./AppointmentReschedulePanel";
import { getAppointmentSchedule } from "../utils/businessTime";
import MonthYearSelects from "./MonthYearSelects";
import { APPOINTMENT_CANCEL_MINIMUM_NOTICE_HOURS } from "../utils/businessTime";
import { getPeriodSelectorLabel, rangeNeedsPeriodSelector } from "../utils/reportRange";

const field =
  "rounded-lg border border-slate-400 bg-white px-2 py-1.5 text-sm text-[#121212] focus:border-[#35783C] focus:outline-none focus:ring-2 focus:ring-[#35783C]/30";
const actionButtonClass =
  "min-h-11 w-full rounded-lg px-2.5 py-1.5 text-xs font-medium transition sm:w-auto focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#35783C]/40 disabled:cursor-not-allowed disabled:opacity-50";

const MODAL_LAYER_Z = "z-[200]";
const CONFIRM_LAYER_Z = "z-[220]";

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
  filterPeriod,
  onFilterPeriodChange,
  viewPeriodOptions = [],
  filterMonth,
  onFilterMonthChange,
  filterYear,
  onFilterYearChange,
  warehouses = [],
  warehouseFilter = "",
  onWarehouseFilterChange,
  emptyMessage = "No hay citas para este filtro.",
  openAppointmentId = null,
  onOpenAppointmentHandled,
  initialAppointmentIdFilter = "",
}) {
  const isStaffRole = role === "Logistica" || role === "Admin" || role === "AdminBodega";
  const canCancelAppointment = role === "Admin" || role === "AdminBodega";
  const canMarkSinRevision = role === "Admin" || role === "AdminBodega";
  const showStaffActions = isStaffRole;
  const [companyFilter, setCompanyFilter] = useState("");
  const [nitFilter, setNitFilter] = useState("");
  const [appointmentIdFilter, setAppointmentIdFilter] = useState("");
  const [confirmCancelId, setConfirmCancelId] = useState(null);
  const [editAppointment, setEditAppointment] = useState(null);
  const [staffActionBusy, setStaffActionBusy] = useState(false);
  const [staffActionError, setStaffActionError] = useState("");
  const editAppointmentId = editAppointment?.id ?? null;

  const runStaffAction = useCallback(async (action) => {
    if (staffActionBusy) return;
    setStaffActionError("");
    setStaffActionBusy(true);
    try {
      await action();
    } catch (err) {
      setStaffActionError(err?.message || "No se pudo completar la acción.");
    } finally {
      setStaffActionBusy(false);
    }
  }, [staffActionBusy]);

  useEffect(() => {
    if (editAppointmentId == null) return;
    const fresh = appointments.find((a) => Number(a.id) === Number(editAppointmentId));
    if (fresh) setEditAppointment(fresh);
  }, [appointments, editAppointmentId]);

  useEffect(() => {
    if (!initialAppointmentIdFilter) return;
    setAppointmentIdFilter(String(initialAppointmentIdFilter));
  }, [initialAppointmentIdFilter]);

  useEffect(() => {
    if (openAppointmentId == null) return;
    const found = appointments.find((a) => Number(a.id) === Number(openAppointmentId));
    if (!found) return;
    setEditAppointment(found);
    setAppointmentIdFilter(String(openAppointmentId));
    onOpenAppointmentHandled?.();
  }, [openAppointmentId, appointments, onOpenAppointmentHandled]);

  useEffect(() => {
    if (!editAppointment) return undefined;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prevOverflow;
    };
  }, [editAppointment]);

  const filteredAppointments = useMemo(() => {
    const companyNeedle = companyFilter.trim().toLowerCase();
    const nitNeedle = nitFilter.replace(/\D/g, "");
    const idNeedle = appointmentIdFilter.replace(/\D/g, "");
    return appointments.filter((a) => {
      const providerName = String(a.provider_name || "").toLowerCase();
      const providerNit = String(a.provider_id || "").replace(/\D/g, "");
      if (companyNeedle && !providerName.includes(companyNeedle)) return false;
      if (nitNeedle && !providerNit.includes(nitNeedle)) return false;
      if (idNeedle && !String(a.id).includes(idNeedle)) return false;
      if (warehouseFilter && Number(a.warehouse_id) !== Number(warehouseFilter)) return false;
      return true;
    });
  }, [appointments, companyFilter, nitFilter, appointmentIdFilter, warehouseFilter]);

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

  const isAdminOrBodega = role === "Admin" || role === "AdminBodega";

  const canExtendDuration = (appointment) => {
    if (
      appointment.status === "cancelado" ||
      appointment.status === "finalizada" ||
      appointment.status === "no_presentada"
    ) {
      return false;
    }
    if (role === "Logistica") {
      if (appointment.status !== "sin_revision") return false;
      return !appointment.logistics_extend_used;
    }
    if (isAdminOrBodega && (appointment.status === "sin_revision" || appointment.status === "revisado")) {
      return true;
    }
    return appointment.status === "sin_revision";
  };

  const renderExtensionNote = (appointment) => {
    const logisticsMin = Number(appointment.logistics_extend_minutes) || 0;
    const totalMin = Number(appointment.total_extend_minutes) || 0;

    // Para evitar incoherencias cuando la cita se reprograma/modifica (y vuelve a una duración anterior),
    // mostramos el resumen simplificado solo desde el cálculo del backend (después del último reset).
    if (isAdminOrBodega) {
      if (totalMin <= 0) return null;
      return (
        <p className="mt-1 text-xs text-amber-800">
          Se aumentó +{totalMin} min sobre la reserva original. Ver Auditorías para más información.
        </p>
      );
    }

    if (role === "Logistica") {
      if (logisticsMin <= 0) return null;
      return (
        <p className="mt-1 text-xs text-amber-800">
          Logística añadió +{logisticsMin} min. Ver Auditorías para más información.
        </p>
      );
    }

    return null;
  };

  const renderStaffActions = (appointment) => {
    if (!canManageAppointment(appointment)) return null;
    const a = appointment;
    const busy = staffActionBusy;
    return (
      <div className="mt-4 flex flex-wrap gap-2">
        {!(role === "Logistica" && a.status === "revisado") && (
          <>
            {canMarkSinRevision && (
              <button
                type="button"
                className={`${actionButtonClass} border border-sky-300 bg-sky-50 text-sky-900 hover:bg-sky-100`}
                disabled={busy || a.status === "sin_revision"}
                onClick={() => void runStaffAction(() => onChangeStatus?.(a.id, "sin_revision"))}
              >
                Marcar sin revisión
              </button>
            )}
            <button
              type="button"
              className={`${actionButtonClass} bg-[#35783C] text-white hover:bg-[#2d6532]`}
              disabled={busy || a.status === "revisado"}
              onClick={() => void runStaffAction(() => onReview(a.id))}
            >
              Marcar revisado
            </button>
            <button
              type="button"
              className={`${actionButtonClass} border border-[#35783C] bg-emerald-50 text-[#121212] hover:bg-emerald-100`}
              disabled={busy || a.status === "finalizada"}
              onClick={() => void runStaffAction(() => onChangeStatus?.(a.id, "finalizada"))}
            >
              Marcar finalizada
            </button>
            <button
              type="button"
              className={`${actionButtonClass} border border-slate-300 bg-slate-100 text-slate-900 hover:bg-slate-200`}
              disabled={busy || a.status === "no_presentada"}
              onClick={() => void runStaffAction(() => onChangeStatus?.(a.id, "no_presentada"))}
            >
              Marcar no presentada
            </button>
            {canCancelAppointment && (
              <button
                type="button"
                className={`${actionButtonClass} border border-rose-300 bg-rose-50 text-rose-900 hover:bg-rose-100`}
                disabled={busy || a.status === "cancelado"}
                onClick={() => setConfirmCancelId(a.id)}
              >
                Cancelar cita
              </button>
            )}
          </>
        )}
        {role === "Logistica" && a.status === "revisado" && (
          <>
            <button
              type="button"
              className={`${actionButtonClass} border border-[#35783C] bg-emerald-50 text-[#121212] hover:bg-emerald-100`}
              disabled={busy}
              onClick={() => void runStaffAction(() => onChangeStatus?.(a.id, "finalizada"))}
            >
              Confirmar finalizada
            </button>
            <button
              type="button"
              className={`${actionButtonClass} border border-slate-300 bg-slate-100 text-slate-900 hover:bg-slate-200`}
              disabled={busy}
              onClick={() => void runStaffAction(() => onChangeStatus?.(a.id, "no_presentada"))}
            >
              Confirmar no presentada
            </button>
          </>
        )}
        {!reviewMode && canExtendDuration(a) && (isAdminOrBodega || !(role === "Logistica" && a.status === "revisado")) && (
          <button
            type="button"
            className={`${actionButtonClass} border border-amber-300 bg-amber-50 text-amber-900 hover:bg-amber-100`}
            disabled={busy}
            onClick={() => void runStaffAction(() => onExtend(a.id, 30))}
          >
            Extender +30 min
          </button>
        )}
        {reviewMode && canExtendDuration(a) && (isAdminOrBodega || !(role === "Logistica" && a.status === "revisado")) && (
          <>
            <button
              type="button"
              className={`${actionButtonClass} border border-amber-300 bg-amber-50 text-amber-900 hover:bg-amber-100`}
              disabled={busy}
              onClick={() => void runStaffAction(() => onExtend(a.id, 30))}
            >
              +30 min
            </button>
            <button
              type="button"
              className={`${actionButtonClass} border border-amber-300 bg-amber-50 text-amber-900 hover:bg-amber-100`}
              disabled={busy}
              onClick={() => void runStaffAction(() => onExtend(a.id, 60))}
            >
              +60 min
            </button>
            <button
              type="button"
              className={`${actionButtonClass} border border-amber-300 bg-amber-50 text-amber-900 hover:bg-amber-100`}
              disabled={busy}
              onClick={() => void runStaffAction(() => onExtend(a.id, 90))}
            >
              +90 min
            </button>
          </>
        )}
      </div>
    );
  };

  const teamDisplayName = (appointment) =>
    appointment.warehouse_unload_team_name?.trim() ||
    (appointment.warehouse_unload_team_id ? `Equipo #${appointment.warehouse_unload_team_id}` : "—");

  const renderAppointmentDetails = (appointment) => {
    const schedule = getAppointmentSchedule(appointment.start_time, appointment.duration_minutes);
    return (
      <>
        <div className="rounded-lg border border-slate-200 bg-slate-50/80 px-3 py-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Ubicación de la cita</p>
          <p className="mt-1 text-sm text-slate-800">
            Cita <span className="font-semibold text-slate-900">#{appointment.id}</span>
          </p>
          <p className="text-sm text-slate-700">
            Bodega: <span className="font-medium">{appointment.warehouse_name || "—"}</span>
          </p>
          <p className="text-sm text-slate-700">
            Equipo: <span className="font-medium">{teamDisplayName(appointment)}</span>
          </p>
        </div>
        <p className="mt-3 text-sm text-slate-600">{appointment.material_description}</p>
        <p className="mt-2 text-sm text-slate-700">
          Proveedor: <span className="font-medium">{appointment.provider_name || "—"}</span> (NIT{" "}
          {appointment.provider_id})
        </p>
        <div className="mt-3 rounded-lg border border-emerald-100 bg-emerald-50/60 px-3 py-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-emerald-900">Horario de la cita</p>
          <p className="mt-1 text-sm capitalize text-slate-800">{schedule.dateLine}</p>
          <p className="text-sm font-medium text-slate-900">
            {schedule.rangeLine}{" "}
            <span className="font-normal text-slate-600">({schedule.durationLabel})</span>
          </p>
          <p className="text-sm text-slate-700">
            Termina a las <span className="font-medium">{schedule.endLine}</span>
          </p>
          {renderExtensionNote(appointment)}
        </div>
        <p className={`mt-2 text-sm ${statusMeta(appointment.status).className}`}>
          Estado: {`${statusMeta(appointment.status).icon} ${statusMeta(appointment.status).label}`}
        </p>
      </>
    );
  };

  const editModal =
    editAppointment &&
    createPortal(
      <div className={`fixed inset-0 ${MODAL_LAYER_Z} flex items-center justify-center p-4`}>
        <button
          type="button"
          className="absolute inset-0 z-0 cursor-default bg-slate-900/55"
          aria-label="Cerrar detalle de cita"
          disabled={staffActionBusy}
          onClick={() => !staffActionBusy && setEditAppointment(null)}
        />
        <div
          className="relative z-10 max-h-[min(90vh,42rem)] w-full max-w-lg overflow-y-auto rounded-xl border border-slate-200 bg-white p-6 shadow-2xl"
          role="dialog"
          aria-modal="true"
          aria-labelledby="appointment-dialog-title"
        >
          <div className="flex items-start justify-between gap-3">
            <h3 id="appointment-dialog-title" className="text-lg font-semibold text-slate-900">
              Cita #{editAppointment.id}
            </h3>
            <button
              type="button"
              className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              disabled={staffActionBusy}
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
          {canManageAppointment(editAppointment) &&
            canRescheduleAppointment(editAppointment) &&
            onReschedule && (
              <AppointmentReschedulePanel
                appointment={editAppointment}
                variant="staff"
                staffRole={role}
                warehouses={warehouses}
                inputClass={field}
                buttonClass={`${actionButtonClass} bg-[#35783C] text-white hover:bg-[#2d6532]`}
                confirmOverlayZIndexClass={CONFIRM_LAYER_Z}
                onReschedule={async (payload) => {
                  await onReschedule(payload);
                  setEditAppointment(null);
                }}
              />
            )}
          {staffActionError && (
            <p className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800" role="alert">
              {staffActionError}
            </p>
          )}
          {staffActionBusy && (
            <p className="mt-2 text-xs text-slate-500" aria-live="polite">
              Guardando cambios…
            </p>
          )}
          {renderStaffActions(editAppointment)}
        </div>
      </div>,
      document.body
    );

  const cancelConfirmDialog = createPortal(
    <ConfirmDialog
      open={confirmCancelId !== null}
      title="Cancelar cita"
      danger
      confirmLabel="Sí, cancelar"
      overlayZIndexClass={CONFIRM_LAYER_Z}
      onCancel={() => setConfirmCancelId(null)}
      onConfirm={() => {
        const id = confirmCancelId;
        setConfirmCancelId(null);
        if (id != null) {
          void runStaffAction(async () => {
            await onChangeStatus?.(id, "cancelado");
          });
        }
      }}
    >
      ¿Seguro que deseas cancelar esta cita? Solo se permite con al menos {APPOINTMENT_CANCEL_MINIMUM_NOTICE_HOURS}{" "}
      horas de anticipación (validado en el servidor).
    </ConfirmDialog>,
    document.body
  );

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
      {cancelConfirmDialog}
      {editModal}
      <h2 className="mb-3 text-lg font-semibold text-slate-900">{title}</h2>

      {isStaffRole && (
        <div className="mb-4 grid gap-3 border-b border-slate-100 pb-4 sm:grid-cols-2 lg:grid-cols-4">
          {!reviewMode && (
            <>
              <div className="sm:col-span-1">
                <label htmlFor="appt-list-view-mode" className="mb-1 block text-xs font-medium text-slate-600">Vista</label>
                <select id="appt-list-view-mode" className={field} value={viewMode} onChange={(e) => onViewModeChange(e.target.value)}>
                  <option value="list">Lista (todas)</option>
                  <option value="day">Por día</option>
                  <option value="week">Por semana</option>
                  <option value="biweekly">Por quincena</option>
                  <option value="month">Por mes</option>
                </select>
              </div>
              {viewMode === "day" && (
                <div className="sm:col-span-1">
                  <label htmlFor="appt-list-filter-day" className="mb-1 block text-xs font-medium text-slate-600">Día</label>
                  <input
                    id="appt-list-filter-day"
                    type="date"
                    className={field + " w-full"}
                    value={filterDay}
                    onChange={(e) => onFilterDayChange(e.target.value)}
                  />
                </div>
              )}
              {(viewMode === "week" || viewMode === "biweekly") && viewPeriodOptions.length > 0 && (
                <div className="sm:col-span-1">
                  <label htmlFor="appt-list-filter-period" className="mb-1 block text-xs font-medium text-slate-600">
                    {getPeriodSelectorLabel(viewMode)}
                  </label>
                  <select
                    id="appt-list-filter-period"
                    className={field + " w-full"}
                    value={filterPeriod ?? 1}
                    onChange={(e) => onFilterPeriodChange(Number(e.target.value))}
                  >
                    {viewPeriodOptions.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              {viewMode === "month" && (
                <MonthYearSelects
                  month={filterMonth}
                  year={filterYear}
                  onMonthChange={onFilterMonthChange}
                  onYearChange={onFilterYearChange}
                  inputClass={field + " w-full"}
                  monthId="appt-list-filter-month"
                  yearId="appt-list-filter-year"
                  cellClassName="sm:col-span-1"
                />
              )}
            </>
          )}
          <div className="sm:col-span-1">
            <label htmlFor="appt-list-filter-company" className="mb-1 block text-xs font-medium text-slate-600">Empresa</label>
            <input
              id="appt-list-filter-company"
              type="text"
              className={field + " w-full"}
              placeholder="Nombre de empresa"
              value={companyFilter}
              onChange={(e) => setCompanyFilter(e.target.value)}
            />
          </div>
          <div className="sm:col-span-1">
            <label htmlFor="appt-list-filter-nit" className="mb-1 block text-xs font-medium text-slate-600">NIT</label>
            <input
              id="appt-list-filter-nit"
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
          {reviewMode && (
            <div className="sm:col-span-1">
              <label htmlFor="appt-list-filter-id" className="mb-1 block text-xs font-medium text-slate-600">
                Número de cita
              </label>
              <input
                id="appt-list-filter-id"
                type="text"
                inputMode="numeric"
                className={field + " w-full"}
                placeholder="Ej. 432"
                value={appointmentIdFilter}
                onChange={(e) => setAppointmentIdFilter(e.target.value.replace(/\D/g, ""))}
              />
            </div>
          )}
          {!reviewMode && onWarehouseFilterChange && warehouses.length > 0 && (
            <div className="sm:col-span-1">
              <label htmlFor="appt-list-filter-warehouse" className="mb-1 block text-xs font-medium text-slate-600">Bodega</label>
              <select
                id="appt-list-filter-warehouse"
                className={field + " w-full"}
                value={warehouseFilter}
                onChange={(e) => onWarehouseFilterChange(e.target.value)}
              >
                <option value="">Todas las bodegas</option>
                {warehouses.map((w) => (
                  <option key={w.id} value={String(w.id)}>
                    {w.name}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      )}

      <div className="space-y-3">
        {filteredAppointments.length === 0 && <p className="text-sm text-slate-500">{emptyMessage}</p>}
        {filteredAppointments.map((a) => {
          const schedule = getAppointmentSchedule(a.start_time, a.duration_minutes);
          return (
          <div key={a.id} className="rounded-lg border border-slate-100 bg-slate-50/80 p-3">
            {showStaffActions ? (
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-slate-900">Cita #{a.id}</p>
                  <p className="truncate text-sm text-slate-600">{a.provider_name || "—"}</p>
                  <p className="text-xs text-slate-600">
                    {a.warehouse_name || "—"} · {teamDisplayName(a)}
                  </p>
                  <p className="text-sm font-medium text-slate-800">{schedule.rangeLine}</p>
                  <p className="text-xs text-slate-600">
                    Termina {schedule.endLine} · {schedule.durationLabel}
                  </p>
                  <p className={`text-sm ${statusMeta(a.status).className}`}>
                    {`${statusMeta(a.status).icon} ${statusMeta(a.status).label}`}
                  </p>
                </div>
                <button
                  type="button"
                  className={`${actionButtonClass} shrink-0 border border-[#35783C] bg-white text-[#35783C] hover:bg-emerald-50`}
                  onClick={() => {
                    setStaffActionError("");
                    setEditAppointment(a);
                  }}
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
        );
        })}
      </div>
    </div>
  );
}
