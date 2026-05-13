import { useEffect, useMemo, useState } from "react";
import api, { API_PREFIX, parseApiResponse } from "../api/client";
import { describeProviderSlotAvailability } from "../utils/providerAvailability";
import {
  DEFAULT_BUSINESS_TZ,
  buildDateTimeIsoInTimeZone,
  formatDateInputInTimeZone,
  formatTimeInputInTimeZone,
} from "../utils/businessTime";

function toMinutes(hhmm) {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
}

function toHHMM(totalMinutes) {
  const h = String(Math.floor(totalMinutes / 60)).padStart(2, "0");
  const m = String(totalMinutes % 60).padStart(2, "0");
  return `${h}:${m}`;
}

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
  const [timeValue, setTimeValue] = useState(() => toTimeInputValue(appointment.start_time));
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

  useEffect(() => {
    setDateValue(toDateInputValue(appointment.start_time, businessTz));
    setTimeValue(toTimeInputValue(appointment.start_time, businessTz));
    setFormError("");
  }, [appointment.id, appointment.start_time, businessTz]);

  useEffect(() => {
    if (variant !== "staff" || !dateValue) return;
    let cancelled = false;
    const run = async () => {
      setLoadingSlots(true);
      setSlotError("");
      try {
        const response = await api.get(`${API_PREFIX}/crud/appointment-franjas/resolved?day=${dateValue}`);
        const payload = parseApiResponse(response);
        if (cancelled) return;
        if (!payload.success) {
          setSlots([]);
          setSlotError("No se pudieron cargar las franjas del día.");
          return;
        }
        const slotMinutes = Number(payload.data?.slot_minutes || 90);
        const resolvedTz = String(payload.data?.timezone || DEFAULT_BUSINESS_TZ);
        setBusinessTz(resolvedTz);
        const franjas = Array.isArray(payload.data?.franjas) ? payload.data.franjas : [];
        const built = [];
        franjas.forEach((window) => {
          const start = toMinutes(String(window.start_local || ""));
          const end = toMinutes(String(window.end_local || ""));
          if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) return;
          for (let t = start; t <= end; t += slotMinutes) {
            built.push(toHHMM(t));
          }
        });
        const candidateTimes = [...new Set(built)].sort();
        const availableTimes = [];
        for (const slot of candidateTimes) {
          const iso = buildDateTimeIsoInTimeZone(dateValue, slot, resolvedTz);
          const conflictResponse = await api.get(`${API_PREFIX}/appointments/conflict-check`, {
            params: {
              start_time: iso,
              duration_minutes: appointment.duration_minutes || 90,
              exclude_appointment_id: appointment.id,
            },
          });
          const conflictPayload = parseApiResponse(conflictResponse);
          if (conflictPayload.success && !conflictPayload.data?.conflict) {
            availableTimes.push(slot);
          }
        }
        if (cancelled) return;
        const times = availableTimes;
        setSlots(times);
        setTimeValue((prev) => (times.includes(prev) ? prev : times[0] || ""));
        if (times.length === 0) {
          setSlotError(
            candidateTimes.length === 0
              ? "Este día no tiene franjas habilitadas o no hay horarios válidos en la cuadrícula de turnos."
              : "Los horarios de la franja ya están ocupados por otras citas."
          );
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
  }, [variant, dateValue, appointment.id, appointment.duration_minutes]);

  useEffect(() => {
    if (variant !== "provider" || !dateValue || !loadProviderDayAvailability) return;
    let cancelled = false;
    const run = async () => {
      setLoadingSlots(true);
      setSlotError("");
      try {
        const result = await loadProviderDayAvailability(dateValue, appointment.id);
        if (cancelled) return;
        const times = Array.isArray(result?.times) ? result.times : [];
        setSlots(times);
        setMinimumNoticeHours(Number(result?.minimumNoticeHours || 24));
        setSlotReason(times.length === 0 ? String(result?.reason || "").trim() : "");
        setSlotMessage(times.length === 0 ? String(result?.message || "").trim() : "");
        setTimeValue((prev) => (times.includes(prev) ? prev : times[0] || ""));
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
      setFormError(usesSlotPicker ? "Selecciona un horario disponible." : "Selecciona una hora.");
      return;
    }
    if (usesSlotPicker && !slots.includes(timeValue)) {
      setFormError("El horario elegido ya no está disponible.");
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
          ? "Elige otro día y hora dentro de las franjas abiertas. Aplica la misma anticipación mínima que al agendar."
          : "Elige la nueva fecha y un horario de la franja habilitada (turnos cada 90 minutos)."}
      </p>
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
          <label className="mb-1 block text-xs font-medium text-slate-600">Nueva hora</label>
          {usesSlotPicker ? (
            <select
              className={inputClass}
              value={timeValue}
              onChange={(event) => setTimeValue(event.target.value)}
              disabled={loadingSlots || slots.length === 0}
            >
              {slots.length === 0 ? (
                <option value="">
                  {variant === "provider" ? availabilityCopy.optionLabel : "Sin horarios disponibles"}
                </option>
              ) : (
                slots.map((slot) => (
                  <option key={slot} value={slot}>
                    {slot}
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
      {variant === "staff" && slotError && (
        <p className="mt-2 text-xs text-amber-800">{slotError}</p>
      )}
      {formError && <p className="mt-2 text-xs text-rose-700">{formError}</p>}
      <button type="submit" className={buttonClass + " mt-3"} disabled={submitting || loadingSlots}>
        {submitting ? "Guardando..." : "Guardar nueva fecha"}
      </button>
    </form>
  );
}
