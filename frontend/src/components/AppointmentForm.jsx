import { useEffect, useMemo, useState } from "react";
import api, { API_PREFIX, parseApiResponse } from "../api/client";

const DRAFT_STORAGE_KEY = "ferragro_appt_form_draft_v1";

const field =
  "mt-1 w-full rounded-lg border border-slate-400 bg-white px-3 py-2.5 text-sm text-[#121212] placeholder:text-slate-500 focus:border-[#35783C] focus:outline-none focus:ring-2 focus:ring-[#35783C]/30";
function dateToISOInput(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function toMinutes(hhmm) {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
}

function toHHMM(totalMinutes) {
  const h = String(Math.floor(totalMinutes / 60)).padStart(2, "0");
  const m = String(totalMinutes % 60).padStart(2, "0");
  return `${h}:${m}`;
}

function resolveDefaultDate(allowedDays) {
  const today = new Date();
  const normalizedDays = Array.from(new Set((allowedDays || []).filter((d) => d >= 1 && d <= 7)));
  if (normalizedDays.length === 0) {
    return dateToISOInput(today);
  }
  for (let i = 0; i < 21; i += 1) {
    const probe = new Date(today);
    probe.setDate(today.getDate() + i);
    const iso = probe.getDay() === 0 ? 7 : probe.getDay();
    if (normalizedDays.includes(iso)) {
      return dateToISOInput(probe);
    }
  }
  return dateToISOInput(today);
}

export default function AppointmentForm({ onSubmit, windowsHint = "", windowsPack = null }) {
  const slotMinutes = Number(windowsPack?.slot_minutes || 90);
  const windows = windowsPack?.franjas || [];
  const defaultDate = resolveDefaultDate([]);
  const [form, setForm] = useState({
    provider_id: "",
    material_description: "",
    appointment_date: defaultDate,
    appointment_time: "",
    duration_minutes: 90,
    status: "sin_revision",
  });
  const [resolvedWindows, setResolvedWindows] = useState([]);
  const [conflict, setConflict] = useState(false);
  const [formError, setFormError] = useState("");

  useEffect(() => {
    try {
      const raw = localStorage.getItem(DRAFT_STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === "object") {
        setForm((prev) => ({ ...prev, ...parsed }));
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    const t = window.setTimeout(() => {
      try {
        localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(form));
      } catch {
        /* ignore */
      }
    }, 500);
    return () => window.clearTimeout(t);
  }, [form]);

  useEffect(() => {
    const nextDefault = resolveDefaultDate([]);
    setForm((prev) => {
      if (prev.appointment_date === nextDefault && prev.appointment_time === "") {
        return prev;
      }
      return {
        ...prev,
        appointment_date: nextDefault,
        appointment_time: "",
      };
    });
  }, [windowsPack]);

  useEffect(() => {
    const run = async () => {
      if (!form.appointment_date) {
        setResolvedWindows([]);
        return;
      }
      try {
        const response = await api.get(`${API_PREFIX}/crud/appointment-franjas/resolved?day=${form.appointment_date}`);
        const payload = parseApiResponse(response);
        if (!payload.success) {
          setResolvedWindows([]);
          return;
        }
        setResolvedWindows(payload.data?.franjas || []);
      } catch {
        setResolvedWindows([]);
      }
    };
    run();
  }, [form.appointment_date]);

  useEffect(() => {
    const run = async () => {
      if (!form.appointment_date || !form.appointment_time) {
        setConflict(false);
        return;
      }
      try {
        const iso = new Date(`${form.appointment_date}T${form.appointment_time}`).toISOString();
        const response = await api.get(
          `${API_PREFIX}/appointments/conflict-check?start_time=${encodeURIComponent(iso)}&duration_minutes=90`
        );
        const payload = parseApiResponse(response);
        if (!payload.success) {
          setConflict(false);
          return;
        }
        setConflict(Boolean(payload.data?.conflict));
      } catch {
        setConflict(false);
      }
    };
    run();
  }, [form.appointment_date, form.appointment_time]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]: name === "provider_id" ? value.replace(/\D/g, "") : value,
    }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!/^\d{10}$/.test(form.provider_id || "")) {
      setFormError("⚠ El NIT del proveedor debe tener exactamente 10 dígitos.");
      return;
    }
    if (!form.material_description.trim()) {
      setFormError("⚠ La descripción del material es obligatoria.");
      return;
    }
    if (!form.appointment_date || !form.appointment_time) {
      setFormError("⚠ Debes seleccionar fecha y hora para agendar la cita.");
      return;
    }
    if (conflict) {
      setFormError("⚠ Existe un conflicto con otra cita. Selecciona otro horario.");
      return;
    }
    setFormError("");
    try {
      localStorage.removeItem(DRAFT_STORAGE_KEY);
    } catch {
      /* ignore */
    }
    onSubmit({
      provider_id: Number(form.provider_id),
      material_description: form.material_description,
      start_time: `${form.appointment_date}T${form.appointment_time}`,
      duration_minutes: 90,
      status: "sin_revision",
    });
  };

  const slots = useMemo(() => {
    if (!form.appointment_date) return [];
    const out = [];
    const sourceWindows = resolvedWindows.length > 0 ? resolvedWindows : windows;
    sourceWindows.forEach((w) => {
      const start = toMinutes(String(w.start_local || ""));
      const end = toMinutes(String(w.end_local || ""));
      if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) return;
      for (let t = start; t <= end; t += slotMinutes) {
        out.push(toHHMM(t));
      }
    });
    return Array.from(new Set(out)).sort();
  }, [form.appointment_date, windows, resolvedWindows, slotMinutes]);

  useEffect(() => {
    setForm((prev) => {
      if (slots.includes(prev.appointment_time)) return prev;
      const nextTime = slots[0] || "";
      if (prev.appointment_time === nextTime) return prev;
      return { ...prev, appointment_time: nextTime };
    });
  }, [slots]);

  return (
    <form onSubmit={handleSubmit} className="grid gap-3 rounded-xl border border-slate-200 bg-white p-5 shadow-sm" noValidate>
      <h2 className="text-base font-semibold text-[#121212]">Agendar nueva cita</h2>
      <label htmlFor="appointment-provider-id" className="text-sm font-medium text-[#121212]">
        NIT proveedor
      </label>
      <input
        id="appointment-provider-id"
        className={field}
        type="text"
        inputMode="numeric"
        name="provider_id"
        placeholder="NIT proveedor (10 dígitos)"
        value={form.provider_id}
        minLength={10}
        maxLength={10}
        pattern="^\d{10}$"
        title="El NIT debe tener exactamente 10 dígitos"
        onChange={handleChange}
        aria-invalid={Boolean(formError)}
        aria-describedby={formError ? "appointment-form-error" : undefined}
        required
      />
      <label htmlFor="appointment-material-description" className="text-sm font-medium text-[#121212]">
        Descripción del material
      </label>
      <textarea
        id="appointment-material-description"
        className={field + " min-h-[88px]"}
        name="material_description"
        placeholder="Descripción del material"
        onChange={handleChange}
        aria-invalid={Boolean(formError)}
        aria-describedby={formError ? "appointment-form-error" : undefined}
        required
      />
      {windowsHint && <p className="text-xs text-emerald-800">{windowsHint}</p>}
      <div className="grid gap-2 md:grid-cols-2">
        <label htmlFor="appointment-date" className="text-sm font-medium text-[#121212]">
          Fecha de la cita
        </label>
        <input id="appointment-date" className={field} type="date" name="appointment_date" value={form.appointment_date} onChange={handleChange} aria-invalid={Boolean(formError)} aria-describedby={formError ? "appointment-form-error" : undefined} required />
        <label htmlFor="appointment-time" className="text-sm font-medium text-[#121212]">
          Hora de la cita
        </label>
        <select
          id="appointment-time"
          className={field}
          name="appointment_time"
          value={form.appointment_time}
          onChange={handleChange}
          required
          disabled={slots.length === 0}
          aria-invalid={Boolean(formError)}
          aria-describedby={formError ? "appointment-form-error" : undefined}
        >
          {slots.length === 0 && <option value="">Sin horas disponibles</option>}
          {slots.map((slot) => (
            <option key={slot} value={slot}>
              {slot}
            </option>
          ))}
        </select>
      </div>
      <p className="text-xs text-slate-500">Intervalo entre citas: {slotMinutes} minutos.</p>
      {formError && (
        <p id="appointment-form-error" className="text-sm font-medium text-rose-700" role="alert" aria-live="assertive">
          {formError}
        </p>
      )}
      {conflict && (
        <p className="text-xs font-medium text-rose-700" role="status" aria-live="polite">
          ⚠ Conflicto detectado: ya existe una cita en ese horario. Cambia la hora antes de guardar.
        </p>
      )}
      <button
        type="submit"
        disabled={slots.length === 0 || conflict}
        className="min-h-11 rounded-lg bg-[#35783C] px-4 py-2.5 text-sm font-semibold text-white shadow-md transition hover:bg-[#2d6532] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#35783C]/40 disabled:cursor-not-allowed disabled:opacity-60"
      >
        Agendar cita
      </button>
    </form>
  );
}
