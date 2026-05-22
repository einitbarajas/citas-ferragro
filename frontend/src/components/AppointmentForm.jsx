import { useEffect, useMemo, useState } from "react";
import api, { API_PREFIX, parseApiResponse } from "../api/client";
import {
  buildSlotsFromFranjas,
  formatSlotLabel,
  parseSlotKey,
  slotKey,
} from "../utils/appointmentSlots";

const DRAFT_STORAGE_KEY = "ferragro_appt_form_draft_v1";

const field =
  "mt-1 w-full rounded-lg border border-slate-400 bg-white px-3 py-2.5 text-sm text-[#121212] placeholder:text-slate-500 focus:border-[#35783C] focus:outline-none focus:ring-2 focus:ring-[#35783C]/30";

function dateToISOInput(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function resolveDefaultDate() {
  return dateToISOInput(new Date());
}

export default function AppointmentForm({
  onSubmit,
  windowsHint = "",
  windowsPack = null,
  warehouses = [],
  warehouseId = null,
  onWarehouseChange,
}) {
  const windows = windowsPack?.franjas || [];
  const defaultDate = resolveDefaultDate();
  const [form, setForm] = useState({
    provider_id: "",
    material_description: "",
    appointment_date: defaultDate,
    appointment_slot: "",
    status: "sin_revision",
  });
  const [resolvedWindows, setResolvedWindows] = useState([]);
  const [unloadTeams, setUnloadTeams] = useState([]);
  const [unloadTeamId, setUnloadTeamId] = useState("");
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
    const run = async () => {
      if (!form.appointment_date || !warehouseId) {
        setResolvedWindows([]);
        return;
      }
      try {
        const response = await api.get(
          `${API_PREFIX}/crud/appointment-franjas/resolved?day=${form.appointment_date}&warehouse_id=${warehouseId}`
        );
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
  }, [form.appointment_date, warehouseId]);

  useEffect(() => {
    const run = async () => {
      if (!warehouseId) {
        setUnloadTeams([]);
        setUnloadTeamId("");
        return;
      }
      try {
        const response = await api.get(`${API_PREFIX}/appointments/unload-teams`, {
          params: { warehouse_id: warehouseId },
        });
        const payload = parseApiResponse(response);
        const teams = Array.isArray(payload.data) ? payload.data : [];
        setUnloadTeams(teams);
        setUnloadTeamId((prev) => {
          if (prev && teams.some((t) => String(t.id) === String(prev))) return prev;
          return teams.length === 1 ? String(teams[0].id) : teams[0]?.id ? String(teams[0].id) : "";
        });
      } catch {
        setUnloadTeams([]);
        setUnloadTeamId("");
      }
    };
    run();
  }, [warehouseId]);

  useEffect(() => {
    const run = async () => {
      const chosen = parseSlotKey(form.appointment_slot);
      const teamId = Number(unloadTeamId);
      if (!form.appointment_date || !chosen || !warehouseId || !Number.isFinite(teamId) || teamId < 1) {
        setConflict(false);
        return;
      }
      try {
        const iso = new Date(`${form.appointment_date}T${chosen.start_local}`).toISOString();
        const response = await api.get(`${API_PREFIX}/appointments/conflict-check`, {
          params: {
            start_time: iso,
            duration_minutes: chosen.duration_minutes,
            warehouse_id: warehouseId,
            unload_team_id: teamId,
          },
        });
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
  }, [form.appointment_date, form.appointment_slot, warehouseId, unloadTeamId]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]: name === "provider_id" ? value.replace(/\D/g, "") : value,
    }));
  };

  const slots = useMemo(() => {
    const sourceWindows = resolvedWindows.length > 0 ? resolvedWindows : windows;
    return buildSlotsFromFranjas(sourceWindows);
  }, [windows, resolvedWindows]);

  useEffect(() => {
    setForm((prev) => {
      const keys = slots.map((s) => slotKey(s));
      if (keys.includes(prev.appointment_slot)) return prev;
      return { ...prev, appointment_slot: keys[0] || "" };
    });
  }, [slots]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!warehouseId) {
      setFormError("⚠ Selecciona una bodega.");
      return;
    }
    const teamId = Number(unloadTeamId);
    if (!Number.isFinite(teamId) || teamId < 1) {
      setFormError("⚠ Selecciona el muelle / equipo de descarga de la bodega.");
      return;
    }
    if (!/^\d{10}$/.test(form.provider_id || "")) {
      setFormError("⚠ El NIT del proveedor debe tener exactamente 10 dígitos.");
      return;
    }
    if (!form.material_description.trim()) {
      setFormError("⚠ La descripción del material es obligatoria.");
      return;
    }
    const chosen = parseSlotKey(form.appointment_slot);
    if (!form.appointment_date || !chosen) {
      setFormError("⚠ Debes seleccionar fecha y turno para agendar la cita.");
      return;
    }
    if (conflict) {
      setFormError("⚠ Existe un conflicto con otra cita. Selecciona otro turno.");
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
      warehouse_id: warehouseId,
      warehouse_unload_team_id: teamId,
      material_description: form.material_description,
      start_time: `${form.appointment_date}T${chosen.start_local}`,
      duration_minutes: chosen.duration_minutes,
      status: "sin_revision",
    });
  };

  return (
    <form onSubmit={handleSubmit} className="grid gap-3 rounded-xl border border-slate-200 bg-white p-5 shadow-sm" noValidate>
      <h2 className="text-base font-semibold text-[#121212]">Agendar nueva cita</h2>
      <label htmlFor="appointment-warehouse" className="text-sm font-medium text-[#121212]">
        Bodega
      </label>
      <select
        id="appointment-warehouse"
        className={field}
        value={warehouseId ?? ""}
        onChange={(e) => onWarehouseChange?.(Number(e.target.value) || null)}
        required
      >
        {warehouses.map((w) => (
          <option key={w.id} value={w.id}>
            {w.name}
          </option>
        ))}
      </select>
      {unloadTeams.length > 0 && (
        <>
          <label htmlFor="appointment-unload-team" className="text-sm font-medium text-[#121212]">
            Muelle / equipo de descarga
          </label>
          <select
            id="appointment-unload-team"
            className={field}
            value={unloadTeamId}
            onChange={(e) => setUnloadTeamId(e.target.value)}
            required
          >
            {unloadTeams.length > 1 && <option value="">Selecciona un muelle…</option>}
            {unloadTeams.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </>
      )}
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
        value={form.material_description}
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
        <input
          id="appointment-date"
          className={field}
          type="date"
          name="appointment_date"
          value={form.appointment_date}
          onChange={handleChange}
          aria-invalid={Boolean(formError)}
          aria-describedby={formError ? "appointment-form-error" : undefined}
          required
        />
        <label htmlFor="appointment-slot" className="text-sm font-medium text-[#121212]">
          Turno
        </label>
        <select
          id="appointment-slot"
          className={field}
          name="appointment_slot"
          value={form.appointment_slot}
          onChange={handleChange}
          required
          disabled={slots.length === 0}
          aria-invalid={Boolean(formError)}
          aria-describedby={formError ? "appointment-form-error" : undefined}
        >
          {slots.length === 0 && <option value="">Sin turnos disponibles</option>}
          {slots.map((slot) => (
            <option key={slotKey(slot)} value={slotKey(slot)}>
              {formatSlotLabel(slot)}
            </option>
          ))}
        </select>
      </div>
      {formError && (
        <p id="appointment-form-error" className="text-sm font-medium text-rose-700" role="alert" aria-live="assertive">
          {formError}
        </p>
      )}
      {conflict && (
        <p className="text-xs font-medium text-rose-700" role="status" aria-live="polite">
          ⚠ Conflicto detectado: ya existe una cita en ese turno. Cambia el horario antes de guardar.
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
