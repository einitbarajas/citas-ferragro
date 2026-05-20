import { useEffect, useMemo, useState } from "react";
import api, { API_PREFIX, parseApiResponse } from "../api/client";
import { describeProviderSlotAvailability } from "../utils/providerAvailability";
import { formatSlotLabel, normalizeAvailableSlots, parseSlotKey, slotKey } from "../utils/appointmentSlots";
import {
  DEFAULT_BUSINESS_TZ,
  buildDateTimeIsoInTimeZone,
  formatDateInputInTimeZone,
  formatTimeInputInTimeZone,
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

export default function AppointmentReschedulePanel({
  appointment,
  variant,
  inputClass,
  buttonClass,
  onReschedule,
  loadProviderDayAvailability,
}) {
  const [dateValue, setDateValue] = useState(() => toDateInputValue(appointment.start_time));
  const [timeValue, setTimeValue] = useState(() => {
    const tz = DEFAULT_BUSINESS_TZ;
    const start = toTimeInputValue(appointment.start_time, tz);
    return `${start}|${appointment.duration_minutes || 60}`;
  });
  const [slots, setSlots] = useState([]);
  const [slotReason, setSlotReason] = useState("");
  const [slotMessage, setSlotMessage] = useState("");
  const [minimumNoticeHours, setMinimumNoticeHours] = useState(24);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [slotError, setSlotError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");
  const [businessTz, setBusinessTz] = useState(DEFAULT_BUSINESS_TZ);
  const usesSlotPicker = variant === "provider" || variant === "staff";
  const warehouseId = appointment.warehouse_id;

  useEffect(() => {
    setDateValue(toDateInputValue(appointment.start_time, businessTz));
    const start = toTimeInputValue(appointment.start_time, businessTz);
    setTimeValue(`${start}|${appointment.duration_minutes || 60}`);
    setFormError("");
  }, [appointment.id, appointment.start_time, appointment.duration_minutes, businessTz]);

  useEffect(() => {
    if (variant !== "staff" || !dateValue || !warehouseId) return;
    let cancelled = false;
    const run = async () => {
      setLoadingSlots(true);
      setSlotError("");
      try {
        const params = new URLSearchParams({
          day: dateValue,
          warehouse_id: String(warehouseId),
          exclude_appointment_id: String(appointment.id),
        });
        const response = await api.get(`${API_PREFIX}/appointments/available-slots?${params.toString()}`);
        const payload = parseApiResponse(response);
        if (cancelled) return;
        if (!payload.success) {
          setSlots([]);
          setSlotError(payload.message || "No se pudieron cargar los turnos del día.");
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
              "Este día no tiene turnos disponibles en la bodega de la cita."
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
  }, [variant, dateValue, appointment.id, appointment.duration_minutes, warehouseId]);

  useEffect(() => {
    if (variant !== "provider" || !dateValue || !loadProviderDayAvailability) return;
    let cancelled = false;
    const run = async () => {
      setLoadingSlots(true);
      setSlotError("");
      try {
        const result = await loadProviderDayAvailability(dateValue, appointment.id);
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
  }, [variant, dateValue, appointment.id, loadProviderDayAvailability]);

  const slotKeys = useMemo(() => slots.map((s) => slotKey(s)), [slots]);

  const availabilityCopy = useMemo(
    () =>
      describeProviderSlotAvailability({
        loading: loadingSlots,
        loadError: slotError,
        hasExistingAppointment: false,
        reason: slotReason,
        message: slotMessage,
        minimumNoticeHours,
        selectedDayOpen: true,
      }),
    [loadingSlots, slotError, slotReason, slotMessage, minimumNoticeHours]
  );

  const onSubmit = async (event) => {
    event.preventDefault();
    setFormError("");
    if (!dateValue) {
      setFormError("Selecciona una fecha.");
      return;
    }
    if (!timeValue) {
      setFormError(usesSlotPicker ? "Selecciona un turno disponible." : "Selecciona una hora.");
      return;
    }
    if (usesSlotPicker) {
      if (!slotKeys.includes(timeValue)) {
        setFormError("El turno elegido ya no está disponible.");
        return;
      }
      const chosen = parseSlotKey(timeValue);
      if (!chosen) {
        setFormError("Turno inválido.");
        return;
      }
      try {
        setSubmitting(true);
        await onReschedule({
          appointmentId: appointment.id,
          startTime: buildLocalDateTimeIso(dateValue, chosen.start_local, businessTz),
        });
      } catch (err) {
        setFormError(err?.message || "No se pudo reprogramar la cita.");
      } finally {
        setSubmitting(false);
      }
      return;
    }
    try {
      setSubmitting(true);
      await onReschedule({
        appointmentId: appointment.id,
        startTime: buildLocalDateTimeIso(dateValue, timeValue, businessTz),
      });
    } catch (err) {
      setFormError(err?.message || "No se pudo reprogramar la cita.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form className="mt-4 rounded-lg border border-slate-200 bg-white p-3" onSubmit={onSubmit}>
      <p className="text-xs font-medium uppercase text-slate-500">Reprogramar cita</p>
      <p className="mt-1 text-xs text-slate-600">
        {variant === "provider"
          ? "Elige otro día y turno dentro de los horarios abiertos en la bodega de tu cita."
          : "Elige la nueva fecha y un turno habilitado en la bodega de la cita."}
      </p>
      {appointment.warehouse_name && (
        <p className="mt-1 text-xs text-slate-500">Bodega: {appointment.warehouse_name}</p>
      )}
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-600">Nueva fecha</label>
          <input
            type="date"
            className={inputClass}
            value={dateValue}
            onChange={(event) => setDateValue(event.target.value)}
            required
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-600">Nuevo turno</label>
          {usesSlotPicker ? (
            <select
              className={inputClass}
              value={timeValue}
              onChange={(event) => setTimeValue(event.target.value)}
              disabled={loadingSlots || slots.length === 0}
            >
              {slots.length === 0 ? (
                <option value="">
                  {variant === "provider" ? availabilityCopy.optionLabel : "Sin turnos disponibles"}
                </option>
              ) : (
                slots.map((slot) => (
                  <option key={slotKey(slot)} value={slotKey(slot)}>
                    {formatSlotLabel(slot)}
                  </option>
                ))
              )}
            </select>
          ) : (
            <input
              type="time"
              className={inputClass}
              value={timeValue}
              onChange={(event) => setTimeValue(event.target.value)}
              required
            />
          )}
        </div>
      </div>
      {variant === "provider" && availabilityCopy.detail && (
        <p className="mt-2 text-xs text-amber-800">{availabilityCopy.detail}</p>
      )}
      {variant === "staff" && slotError && <p className="mt-2 text-xs text-amber-800">{slotError}</p>}
      {formError && <p className="mt-2 text-xs text-rose-700">{formError}</p>}
      <button type="submit" className={buttonClass + " mt-3"} disabled={submitting || loadingSlots}>
        {submitting ? "Guardando..." : "Guardar nueva fecha"}
      </button>
    </form>
  );
}
