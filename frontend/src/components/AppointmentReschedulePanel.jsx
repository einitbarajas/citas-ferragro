import { useEffect, useMemo, useState } from "react";
import api, {
  API_PREFIX,
  isAppointmentSlotWindowMismatch,
  parseApiError,
  parseApiResponse,
} from "../api/client";
import ConfirmDialog from "./ConfirmDialog";
import StaffAppointmentChangeConfirm from "./StaffAppointmentChangeConfirm";
import { describeProviderSlotAvailability } from "../utils/providerAvailability";
import { formatSlotLabel, normalizeAvailableSlots, parseSlotKey, slotKey } from "../utils/appointmentSlots";
import {
  DEFAULT_BUSINESS_TZ,
  buildDateTimeIsoInTimeZone,
  formatDateInputInTimeZone,
  formatTimeInputInTimeZone,
  getAppointmentSchedule,
  todayISOInTimeZone,
} from "../utils/businessTime";

function toDateInputValue(isoString, timeZone = DEFAULT_BUSINESS_TZ) {
  return formatDateInputInTimeZone(isoString, timeZone);
}

function toTimeInputValue(isoString, timeZone = DEFAULT_BUSINESS_TZ) {
  return formatTimeInputInTimeZone(isoString, timeZone);
}

function buildLocalDateTimeIso(dateValue, timeValue, timeZone = DEFAULT_BUSINESS_TZ) {
  return buildDateTimeIsoInTimeZone(dateValue, timeValue, timeZone);
}

function teamLabel(team) {
  if (!team) return "—";
  return team.name?.trim() || `Equipo #${team.id}`;
}

export default function AppointmentReschedulePanel({
  appointment,
  variant,
  staffRole,
  warehouses = [],
  inputClass,
  buttonClass,
  onReschedule,
  loadProviderDayAvailability,
  confirmOverlayZIndexClass = "z-[110]",
}) {
  const [dateValue, setDateValue] = useState(() => toDateInputValue(appointment.start_time));
  const [timeValue, setTimeValue] = useState(() => {
    const tz = DEFAULT_BUSINESS_TZ;
    const start = toTimeInputValue(appointment.start_time, tz);
    return `${start}|${appointment.duration_minutes || 60}`;
  });
  const [warehouseId, setWarehouseId] = useState(String(appointment.warehouse_id || ""));
  const [unloadTeamId, setUnloadTeamId] = useState(
    appointment.warehouse_unload_team_id ? String(appointment.warehouse_unload_team_id) : ""
  );
  const [unloadTeams, setUnloadTeams] = useState([]);
  const [slots, setSlots] = useState([]);
  const [slotReason, setSlotReason] = useState("");
  const [slotMessage, setSlotMessage] = useState("");
  const [minimumNoticeHours, setMinimumNoticeHours] = useState(24);
  const [loadingTeams, setLoadingTeams] = useState(false);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [slotError, setSlotError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");
  const [businessTz, setBusinessTz] = useState(DEFAULT_BUSINESS_TZ);
  const [saveConfirmOpen, setSaveConfirmOpen] = useState(false);
  const [pendingSavePayload, setPendingSavePayload] = useState(null);
  const [overrideConfirmOpen, setOverrideConfirmOpen] = useState(false);
  const [overrideErrorMessage, setOverrideErrorMessage] = useState("");
  const [pendingOverridePayload, setPendingOverridePayload] = useState(null);

  const usesSlotPicker = variant === "provider" || variant === "staff";
  const minBookableDate = todayISOInTimeZone(businessTz);
  const canChangeWarehouse = variant === "staff" && staffRole === "Admin";
  const canChangeTeam = variant === "staff" && (staffRole === "Admin" || staffRole === "AdminBodega");
  const effectiveWarehouseId = canChangeWarehouse ? warehouseId : String(appointment.warehouse_id || "");
  const effectiveTeamId = canChangeTeam
    ? unloadTeamId
    : appointment.warehouse_unload_team_id
      ? String(appointment.warehouse_unload_team_id)
      : "";

  useEffect(() => {
    setDateValue(toDateInputValue(appointment.start_time, businessTz));
    const start = toTimeInputValue(appointment.start_time, businessTz);
    setTimeValue(`${start}|${appointment.duration_minutes || 60}`);
    setWarehouseId(String(appointment.warehouse_id || ""));
    setUnloadTeamId(appointment.warehouse_unload_team_id ? String(appointment.warehouse_unload_team_id) : "");
    setFormError("");
  }, [
    appointment.id,
    appointment.start_time,
    appointment.duration_minutes,
    appointment.warehouse_id,
    appointment.warehouse_unload_team_id,
    businessTz,
  ]);

  useEffect(() => {
    if (variant !== "staff" || (!canChangeTeam && !canChangeWarehouse)) return;
    const whId = Number(effectiveWarehouseId);
    if (!Number.isFinite(whId) || whId < 1) {
      setUnloadTeams([]);
      setUnloadTeamId("");
      return;
    }
    let cancelled = false;
    const run = async () => {
      setLoadingTeams(true);
      try {
        const response = await api.get(`${API_PREFIX}/appointments/unload-teams`, {
          params: { warehouse_id: whId },
        });
        const payload = parseApiResponse(response);
        if (cancelled) return;
        const teams = Array.isArray(payload.data) ? payload.data : [];
        setUnloadTeams(teams);
        setUnloadTeamId((prev) => {
          if (prev && teams.some((t) => String(t.id) === String(prev))) return prev;
          return teams[0]?.id ? String(teams[0].id) : "";
        });
      } catch {
        if (!cancelled) {
          setUnloadTeams([]);
          setUnloadTeamId("");
        }
      } finally {
        if (!cancelled) setLoadingTeams(false);
      }
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, [variant, canChangeTeam, canChangeWarehouse, effectiveWarehouseId]);

  useEffect(() => {
    if (variant !== "staff" || !dateValue || !effectiveWarehouseId || !effectiveTeamId) return;
    let cancelled = false;
    const run = async () => {
      setLoadingSlots(true);
      setSlotError("");
      try {
        const params = new URLSearchParams({
          day: dateValue,
          warehouse_id: String(effectiveWarehouseId),
          unload_team_id: String(effectiveTeamId),
          exclude_appointment_id: String(appointment.id),
        });
        const response = await api.get(`${API_PREFIX}/appointments/available-slots?${params.toString()}`);
        const payload = parseApiResponse(response);
        if (cancelled) return;
        if (!payload.success) {
          setSlots([]);
          setSlotError(payload.message || "No se pudieron cargar las franjas del día.");
          return;
        }
        const resolvedTz = String(payload.data?.timezone || DEFAULT_BUSINESS_TZ);
        setBusinessTz(resolvedTz);
        const availableSlots = normalizeAvailableSlots(payload.data);
        if (cancelled) return;
        setSlots(availableSlots);
        const keys = availableSlots.map((s) => slotKey(s));
        setTimeValue((prev) => (keys.includes(prev) ? prev : keys[0] || ""));
        if (availableSlots.length === 0) {
          setSlotError(
            payload.data?.unavailable_message ||
              "Este día no tiene franjas disponibles para la bodega y el equipo seleccionados."
          );
        } else {
          setSlotError("");
        }
      } catch (err) {
        if (cancelled) return;
        setSlots([]);
        setSlotError(err?.message || "No se pudo cargar la disponibilidad.");
      } finally {
        if (!cancelled) setLoadingSlots(false);
      }
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, [variant, dateValue, appointment.id, effectiveWarehouseId, effectiveTeamId]);

  useEffect(() => {
    if (variant !== "provider" || !dateValue || !loadProviderDayAvailability) return;
    let cancelled = false;
    const run = async () => {
      setLoadingSlots(true);
      setSlotError("");
      try {
        const result = await loadProviderDayAvailability(dateValue, appointment.id, effectiveTeamId);
        if (cancelled) return;
        const normalized = normalizeAvailableSlots({
          available_slots: result?.slots,
          available_times: result?.times,
        });
        setSlots(normalized);
        setMinimumNoticeHours(Number(result?.minimumNoticeHours || 24));
        setSlotReason(normalized.length === 0 ? String(result?.reason || "").trim() : "");
        setSlotMessage(normalized.length === 0 ? String(result?.message || "").trim() : "");
        const keys = normalized.map((s) => slotKey(s));
        setTimeValue((prev) => (keys.includes(prev) ? prev : keys[0] || ""));
      } catch (err) {
        if (cancelled) return;
        setSlots([]);
        setSlotReason("");
        setSlotMessage("");
        setSlotError(err?.message || "No se pudo cargar la disponibilidad.");
      } finally {
        if (!cancelled) setLoadingSlots(false);
      }
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, [variant, dateValue, appointment.id, effectiveTeamId, loadProviderDayAvailability]);

  const slotKeys = useMemo(() => slots.map((s) => slotKey(s)), [slots]);

  function addMinutesToLocalTime(startLocal, minutesToAdd) {
    const [sh, sm] = String(startLocal || "")
      .split(":")
      .map((v) => Number(v));
    const add = Number(minutesToAdd);
    if (!Number.isFinite(sh) || !Number.isFinite(sm) || !Number.isFinite(add)) return "";
    const total = sh * 60 + sm + add;
    const wrapped = ((total % 1440) + 1440) % 1440; // permite cruzar el día
    const eh = Math.floor(wrapped / 60);
    const em = wrapped % 60;
    return `${String(eh).padStart(2, "0")}:${String(em).padStart(2, "0")}`;
  }

  const syntheticSelectedSlotLabel = useMemo(() => {
    if (!usesSlotPicker) return null;
    const parsed = parseSlotKey(timeValue);
    if (!parsed) return null;
    if (slotKeys.includes(timeValue)) return null; // ya está entre las franjas disponibles
    const endLocal = addMinutesToLocalTime(parsed.start_local, parsed.duration_minutes);
    if (!endLocal) return null;
    return formatSlotLabel({
      start_local: parsed.start_local,
      end_local: endLocal,
      duration_minutes: parsed.duration_minutes,
    });
  }, [usesSlotPicker, timeValue, slotKeys]);

  const selectedWarehouseName = useMemo(() => {
    const fromList = warehouses.find((w) => String(w.id) === String(effectiveWarehouseId))?.name;
    if (fromList) return fromList;
    return appointment.warehouse_name || "—";
  }, [warehouses, effectiveWarehouseId, appointment.warehouse_name]);

  const selectedTeamName = useMemo(() => {
    const fromList = unloadTeams.find((t) => String(t.id) === String(effectiveTeamId));
    if (fromList) return teamLabel(fromList);
    return appointment.warehouse_unload_team_name || (effectiveTeamId ? `Equipo #${effectiveTeamId}` : "—");
  }, [unloadTeams, effectiveTeamId, appointment.warehouse_unload_team_name]);

  const availabilityCopy = useMemo(
    () =>
      describeProviderSlotAvailability({
        loading: loadingSlots,
        loadError: slotError,
        reason: slotReason,
        message: slotMessage,
        minimumNoticeHours,
        selectedDayOpen: false,
        hasAvailableSlots: slotKeys.length > 0,
      }),
    [loadingSlots, slotError, slotReason, slotMessage, minimumNoticeHours, slotKeys.length]
  );

  const buildStaffPayload = (chosen, { confirmOverride = false, staffChangeReason = "" } = {}) => {
    const payload = {
      appointmentId: appointment.id,
      startTime: buildLocalDateTimeIso(dateValue, chosen.start_local, businessTz),
      durationMinutes: chosen.duration_minutes,
    };
    if (canChangeWarehouse && effectiveWarehouseId) {
      payload.warehouseId = Number(effectiveWarehouseId);
    }
    if (canChangeTeam && effectiveTeamId) {
      payload.warehouseUnloadTeamId = Number(effectiveTeamId);
    }
    if (confirmOverride) {
      payload.confirmNonStandardSlot = true;
      payload.staffChangeReason = staffChangeReason;
    }
    return payload;
  };

  const proposedScheduleSummary = useMemo(() => {
    const chosen = parseSlotKey(timeValue);
    if (!chosen || !dateValue) return "";
    const iso = buildLocalDateTimeIso(dateValue, chosen.start_local, businessTz);
    if (!iso) return "";
    const schedule = getAppointmentSchedule(iso, chosen.duration_minutes, businessTz);
    return `${schedule.dateLine} · ${schedule.rangeLine} (${schedule.durationLabel})`;
  }, [timeValue, dateValue, businessTz]);

  const currentScheduleSummary = useMemo(() => {
    const schedule = getAppointmentSchedule(
      appointment.start_time,
      appointment.duration_minutes,
      businessTz
    );
    return `${schedule.dateLine} · ${schedule.rangeLine} (${schedule.durationLabel})`;
  }, [appointment.start_time, appointment.duration_minutes, businessTz]);

  const submitReschedule = async (payload) => {
    await onReschedule(payload);
    setSaveConfirmOpen(false);
    setPendingSavePayload(null);
    setOverrideConfirmOpen(false);
    setPendingOverridePayload(null);
    setOverrideErrorMessage("");
  };

  const executeSave = async (payload) => {
    try {
      setSubmitting(true);
      await submitReschedule(payload);
    } catch (err) {
      if (variant === "staff" && isAppointmentSlotWindowMismatch(err)) {
        setOverrideErrorMessage(parseApiError(err));
        setPendingOverridePayload(payload);
        setOverrideConfirmOpen(true);
        setSaveConfirmOpen(false);
        setFormError("");
      } else {
        setFormError(err?.message || "No se pudo reprogramar la cita.");
        setSaveConfirmOpen(false);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const buildSavePayload = () => {
    if (usesSlotPicker) {
      const chosen = parseSlotKey(timeValue);
      if (!chosen) return null;
      if (variant === "staff") {
        return buildStaffPayload(chosen);
      }
      return {
        appointmentId: appointment.id,
        startTime: buildLocalDateTimeIso(dateValue, chosen.start_local, businessTz),
        durationMinutes: chosen.duration_minutes,
      };
    }
    return {
      appointmentId: appointment.id,
      startTime: buildLocalDateTimeIso(dateValue, timeValue, businessTz),
    };
  };

  const onSubmit = (event) => {
    event.preventDefault();
    setFormError("");
    if (!dateValue) {
      setFormError("Selecciona una fecha.");
      return;
    }
    if (variant === "provider" && dateValue < minBookableDate) {
      setFormError("No puedes reprogramar a un día que ya pasó. Elige hoy o una fecha futura.");
      return;
    }
    if (variant === "staff" && canChangeTeam && !effectiveTeamId) {
      setFormError("Selecciona un equipo de descarga.");
      return;
    }
    if (!timeValue) {
      setFormError(usesSlotPicker ? "Selecciona una franja horaria disponible." : "Selecciona una hora.");
      return;
    }
    if (usesSlotPicker && !slotKeys.includes(timeValue)) {
      setFormError("La franja elegida ya no está disponible. Elige otra.");
      return;
    }
    const payload = buildSavePayload();
    if (!payload) {
      setFormError("Franja horaria inválida.");
      return;
    }
    setPendingSavePayload(payload);
    setSaveConfirmOpen(true);
  };

  const onConfirmSave = () => {
    if (!pendingSavePayload) return;
    void executeSave(pendingSavePayload);
  };

  const onConfirmOverride = async (reason) => {
    const chosen = parseSlotKey(timeValue);
    if (!chosen) return;
    const base = pendingOverridePayload || pendingSavePayload || buildStaffPayload(chosen);
    if (!base) return;
    try {
      setSubmitting(true);
      await submitReschedule({
        ...base,
        confirmNonStandardSlot: true,
        staffChangeReason: reason,
      });
    } catch (err) {
      setFormError(err?.message || "No se pudo confirmar el cambio.");
      setOverrideConfirmOpen(false);
    } finally {
      setSubmitting(false);
    }
  };

  const staffGridCols = canChangeWarehouse && canChangeTeam ? "sm:grid-cols-2" : "";

  return (
    <form className="mt-4 rounded-lg border border-slate-200 bg-white p-3" onSubmit={onSubmit}>
      <p className="text-xs font-medium uppercase text-slate-500">Reprogramar cita</p>
      <p className="mt-1 text-xs text-slate-600">
        {variant === "provider"
          ? "Elige otro día y franja dentro de los horarios abiertos en la bodega de tu cita."
          : staffRole === "Admin"
            ? "Puedes cambiar bodega, equipo, fecha y franja horaria. Los cambios se validan en el servidor."
            : staffRole === "AdminBodega"
              ? "Puedes cambiar equipo, fecha y franja horaria en tu bodega. Los cambios se validan en el servidor."
              : "Elige la nueva fecha y una franja habilitada en la bodega y el equipo de la cita."}
      </p>
      {variant === "staff" && (
        <p className="mt-1 text-xs text-slate-500">
          Puedes agendar citas consecutivas en el mismo equipo (por ejemplo una de 1:00 a 2:00 y otra de 2:00 a 3:00)
          si cada una usa su franja. Si el sistema advierte un horario distinto, podrás confirmar el cambio indicando el
          motivo.
        </p>
      )}

      {variant === "staff" && (
        <div className="mt-3 rounded-lg border border-slate-100 bg-slate-50/80 px-3 py-2 text-xs text-slate-700">
          <p>
            <span className="font-medium text-slate-900">Cita #{appointment.id}</span>
            {" · "}
            Bodega: <span className="font-medium">{selectedWarehouseName}</span>
            {" · "}
            Equipo: <span className="font-medium">{selectedTeamName}</span>
          </p>
        </div>
      )}

      <div className={`mt-3 grid gap-2 ${staffGridCols}`}>
        {variant === "staff" && canChangeWarehouse && warehouses.length > 0 && (
          <div>
            <label htmlFor={`reschedule-warehouse-${appointment.id}`} className="mb-1 block text-xs font-medium text-slate-600">
              Bodega
            </label>
            <select
              id={`reschedule-warehouse-${appointment.id}`}
              className={inputClass}
              value={warehouseId}
              onChange={(event) => setWarehouseId(event.target.value)}
              required
            >
              {warehouses.map((w) => (
                <option key={w.id} value={String(w.id)}>
                  {w.name}
                </option>
              ))}
            </select>
          </div>
        )}
        {variant === "staff" && canChangeTeam && (
          <div>
            <label htmlFor={`reschedule-team-${appointment.id}`} className="mb-1 block text-xs font-medium text-slate-600">
              Equipo de descarga
            </label>
            <select
              id={`reschedule-team-${appointment.id}`}
              className={inputClass}
              value={unloadTeamId}
              onChange={(event) => setUnloadTeamId(event.target.value)}
              disabled={loadingTeams || unloadTeams.length === 0}
              required
            >
              {unloadTeams.length === 0 ? (
                <option value="">{loadingTeams ? "Cargando equipos…" : "Sin equipos en esta bodega"}</option>
              ) : (
                unloadTeams.map((team) => (
                  <option key={team.id} value={String(team.id)}>
                    {teamLabel(team)}
                  </option>
                ))
              )}
            </select>
          </div>
        )}
        <div>
          <label htmlFor={`reschedule-date-${appointment.id}`} className="mb-1 block text-xs font-medium text-slate-600">
            Nueva fecha
          </label>
          <input
            id={`reschedule-date-${appointment.id}`}
            type="date"
            className={inputClass}
            value={dateValue}
            min={variant === "provider" ? minBookableDate : undefined}
            onChange={(event) => setDateValue(event.target.value)}
            required
          />
        </div>
        <div>
          <label htmlFor={`reschedule-slot-${appointment.id}`} className="mb-1 block text-xs font-medium text-slate-600">
            Franja horaria
          </label>
          {usesSlotPicker ? (
            <select
              id={`reschedule-slot-${appointment.id}`}
              className={inputClass}
              value={timeValue}
              onChange={(event) => setTimeValue(event.target.value)}
              disabled={loadingSlots || slots.length === 0 || loadingTeams}
            >
              {slots.length === 0 ? (
                <option value="">
                  {variant === "provider" ? availabilityCopy.optionLabel : "Sin franjas disponibles"}
                </option>
              ) : (
                slots.map((slot) => (
                  <option key={slotKey(slot)} value={slotKey(slot)}>
                    {formatSlotLabel(slot)}
                  </option>
                ))
              )}
              {syntheticSelectedSlotLabel ? (
                <option value={timeValue}>{syntheticSelectedSlotLabel}</option>
              ) : null}
            </select>
          ) : (
            <input
              id={`reschedule-slot-${appointment.id}`}
              type="time"
              className={inputClass}
              value={timeValue}
              onChange={(event) => setTimeValue(event.target.value)}
              required
            />
          )}
        </div>
      </div>
      {variant === "provider" && loadingSlots && (
        <p className="mt-2 text-xs text-slate-500">Consultando franjas disponibles…</p>
      )}
      {variant === "provider" && !loadingSlots && slotKeys.length === 0 && availabilityCopy.detail && (
        <p className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-2 text-xs leading-relaxed text-amber-950">
          {availabilityCopy.detail}
        </p>
      )}
      {variant === "staff" && slotError && <p className="mt-2 text-xs text-amber-800">{slotError}</p>}
      {formError && <p className="mt-2 text-xs text-rose-700">{formError}</p>}
      <button
        type="submit"
        className={buttonClass + " mt-3"}
        disabled={submitting || loadingSlots || loadingTeams}
      >
        {submitting ? "Guardando..." : "Guardar cambios"}
      </button>

      <ConfirmDialog
        open={saveConfirmOpen}
        title="¿Confirmar cambio de cita?"
        confirmLabel="Sí, cambiar cita"
        cancelLabel="Cancelar"
        overlayZIndexClass={confirmOverlayZIndexClass}
        onCancel={() => {
          setSaveConfirmOpen(false);
          setPendingSavePayload(null);
        }}
        onConfirm={onConfirmSave}
      >
        <p>
          ¿Estás seguro de que deseas guardar los cambios en la <strong>cita #{appointment.id}</strong>?
        </p>
        <p className="mt-2 text-xs text-slate-500">
          Bodega: <span className="font-medium text-slate-700">{selectedWarehouseName}</span>
          {" · "}
          Equipo: <span className="font-medium text-slate-700">{selectedTeamName}</span>
        </p>
        {currentScheduleSummary ? (
          <p className="mt-2 text-xs text-slate-600">
            <span className="font-semibold text-slate-800">Horario actual:</span> {currentScheduleSummary}
          </p>
        ) : null}
        {proposedScheduleSummary ? (
          <p className="mt-1 text-xs text-slate-600">
            <span className="font-semibold text-slate-800">Horario nuevo:</span> {proposedScheduleSummary}
          </p>
        ) : null}
      </ConfirmDialog>

      <StaffAppointmentChangeConfirm
        open={overrideConfirmOpen}
        warningMessage={
          overrideErrorMessage ||
          "El horario elegido no coincide exactamente con un turno estándar. Si estás seguro (por ejemplo, citas con horarios distintos o consecutivos), confirma e indica el motivo."
        }
        currentSummary={currentScheduleSummary}
        proposedSummary={proposedScheduleSummary}
        onCancel={() => {
          setOverrideConfirmOpen(false);
          setPendingOverridePayload(null);
          setOverrideErrorMessage("");
        }}
        onConfirm={onConfirmOverride}
        overlayZIndexClass={confirmOverlayZIndexClass}
      />
    </form>
  );
}
