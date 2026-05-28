import { lazy, Suspense, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  isNarrowPanelTourViewport,
  manualTourBootDelayMs,
  MODULE_TO_NAV_TOUR_ID,
  scrollDashboardSidebarNavItemIntoView,
  TOUR_DASHBOARD_SIDEBAR_SELECTOR,
} from "../guidedTour/panelUtils";
import api, {
  API_PREFIX,
  API_SLOW_TIMEOUT_MS,
  isApiTimeoutError,
  isAppointmentSlotConflict,
  parseApiError,
  parseApiResponse,
  warmApi,
} from "../api/client";
import {
  deriveWarehousesFromAppointments,
  isApiRouteMissing,
} from "../api/apiCompatibility";
import ApiStaleBanner from "../components/ApiStaleBanner";
import ConfirmDialog from "../components/ConfirmDialog";
import FranjaRowsTable from "../components/FranjaRowsTable";
import BrandLogo from "../components/BrandLogo";
import MonthYearSelects from "../components/MonthYearSelects";
import StaffRangeFilterGrid from "../components/StaffRangeFilterGrid";
import NotificationCenter from "../components/NotificationCenter";
import ProviderAppointmentNotificationModal from "../components/ProviderAppointmentNotificationModal";
import PasswordVisibilityButton from "../components/PasswordVisibilityButton";
import ThemeToggle from "../components/ThemeToggle";

const GuidedTourDialog = lazy(() => import("../components/GuidedTourDialog"));
const AppointmentForm = lazy(() => import("../components/AppointmentForm"));
const AppointmentList = lazy(() => import("../components/AppointmentList"));
const AppointmentReschedulePanel = lazy(() => import("../components/AppointmentReschedulePanel"));
import { useAuth } from "../context/AuthContext";
import {
  describeProviderSlotAvailability,
  unwrapProviderDayAvailability,
} from "../utils/providerAvailability";
import {
  formatReportRangeLabel,
  getAnalyticsPeriodOptions,
  getDefaultPeriodIndex,
  getPeriodSelectorLabel,
  getReportRangeBounds,
  rangeNeedsPeriodSelector,
  referenceDateForMonthYear,
} from "../utils/reportRange";
import {
  buildSlotsFromFranjas,
  formatSlotLabel,
  formatLocalTime12h,
  normalizeAvailableSlots,
  parseSlotKey,
  slotDurationMinutes,
  slotKey,
} from "../utils/appointmentSlots";
import {
  summarizeAppointmentsByLocalDay,
  todayISOInTimeZone,
} from "../utils/businessTime";

const appointmentSectionFallback = (
  <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
    Cargando citas…
  </div>
);

function todayISO() {
  return dateISOFrom(new Date());
}

function dateISOFrom(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

const DEFAULT_BUSINESS_TZ = "America/Bogota";

/** YYYY-MM-DD del instante de cita en la zona operativa (misma lógica que el backend). */
function calendarDayISOInTimeZone(isoString, timeZone) {
  const d = new Date(isoString);
  if (Number.isNaN(d.getTime())) return "";
  const tz = timeZone || DEFAULT_BUSINESS_TZ;
  try {
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone: tz,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).formatToParts(d);
    const y = parts.find((p) => p.type === "year")?.value;
    const m = parts.find((p) => p.type === "month")?.value;
    const day = parts.find((p) => p.type === "day")?.value;
    if (y && m && day) return `${y}-${m}-${day}`;
  } catch {
    /* ignore */
  }
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function saludoHorario() {
  const h = new Date().getHours();
  if (h < 12) return "Buenos días";
  if (h < 19) return "Buenas tardes";
  return "Buenas noches";
}

const ADMIN_NAV = [
  { type: "label", text: "Principal" },
  { type: "item", id: "citas", label: "Citas" },
  { type: "item", id: "buscar_citas", label: "Buscar citas" },
  { type: "item", id: "revision_citas", label: "Revision de citas" },
  { type: "label", text: "Informes" },
  { type: "item", id: "analitica", label: "Analítica" },
  { type: "label", text: "Operación" },
  { type: "item", id: "bodegas", label: "Bodegas" },
  { type: "item", id: "horarios", label: "Franjas horarias" },
  { type: "label", text: "Administración" },
  { type: "item", id: "equipo", label: "Equipo (Admin / Logística)" },
  { type: "item", id: "proveedores", label: "Proveedores" },
  { type: "item", id: "auditoria", label: "Auditoría" },
  { type: "item", id: "configuraciones", label: "Configuraciones" },
];

/** Panel operativo por bodega(s) asignadas (sin administración global). */
const ADMIN_BODEGA_NAV = [
  { type: "label", text: "Principal" },
  { type: "item", id: "citas", label: "Citas" },
  { type: "item", id: "buscar_citas", label: "Buscar citas" },
  { type: "item", id: "revision_citas", label: "Revision de citas" },
  { type: "label", text: "Operación" },
  { type: "item", id: "bodegas", label: "Bodegas" },
  { type: "item", id: "horarios", label: "Franjas horarias" },
  { type: "item", id: "auditoria", label: "Auditoría" },
  { type: "item", id: "configuraciones", label: "Configuraciones" },
];

const ROLE_LABELS = {
  Admin: "Administrador",
  AdminBodega: "Administrador de bodega",
  Logistica: "Logística",
  Proveedor: "Proveedor",
};

const roleNeedsWarehouses = (roleName) => roleName === "AdminBodega" || roleName === "Logistica";

function resolveWarehouseIdsForRole(roleName, selectedIds) {
  if (!roleNeedsWarehouses(roleName)) return [];
  return (selectedIds || [])
    .map((id) => Number(id))
    .filter((id) => Number.isFinite(id) && id > 0);
}

function warehouseScopeHint(roleName) {
  if (roleName === "Logistica") {
    return "Marca una o más bodegas. Logística solo opera en esas bodegas (citas, revisión, búsqueda e historial), sin configurar franjas ni administración global.";
  }
  if (roleName === "AdminBodega") {
    return "Marca una o más bodegas. Puede cancelar y modificar citas, gestionar franjas horarias y consultar auditoría de cambios, solo dentro de ese alcance.";
  }
  return "";
}

function formatUserWarehousesLabel(roleName, warehouseIds, warehouses) {
  if (!roleNeedsWarehouses(roleName)) return "—";
  if (!Array.isArray(warehouseIds) || warehouseIds.length === 0) return "Sin bodegas asignadas";
  const names = warehouseIds.map((id) => warehouses.find((w) => w.id === id)?.name || id);
  if (names.length === 1) return names[0];
  return `${names.length} bodegas: ${names.join(", ")}`;
}

const card = "rounded-xl border border-slate-200 bg-white p-5 shadow-sm";
const inlay = "rounded-lg border border-slate-200 bg-slate-50/90 p-4";
const TOAST_AUTO_DISMISS_MS = 5000;
const WAREHOUSE_SAVE_FLASH_KEY = "ferragro_warehouse_save_flash_v1";

function stashWarehouseSaveFlash(message) {
  if (!message) return;
  try {
    sessionStorage.setItem(WAREHOUSE_SAVE_FLASH_KEY, message);
  } catch {
    /* ignore */
  }
}

function consumeWarehouseSaveFlash() {
  try {
    const message = sessionStorage.getItem(WAREHOUSE_SAVE_FLASH_KEY);
    if (message) sessionStorage.removeItem(WAREHOUSE_SAVE_FLASH_KEY);
    return message || "";
  } catch {
    return "";
  }
}
const input =
  "w-full rounded-lg border border-slate-400 bg-white px-3 py-2 text-sm text-[#121212] placeholder:text-slate-500 focus:border-[#35783C] focus:outline-none focus:ring-2 focus:ring-[#35783C]/30";
const btnPrimary =
  "min-h-11 rounded-lg bg-[#35783C] px-4 py-2.5 text-sm font-semibold text-white shadow-md shadow-emerald-900/10 transition hover:bg-[#2d6532] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#35783C]/40 disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-60";
const btnGhost =
  "min-h-11 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-[#121212] shadow-sm transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#35783C]/40";
const BULK_WEEKDAY_OPTIONS = [
  { iso: 1, label: "Lun" },
  { iso: 2, label: "Mar" },
  { iso: 3, label: "Mié" },
  { iso: 4, label: "Jue" },
  { iso: 5, label: "Vie" },
  { iso: 6, label: "Sáb" },
  { iso: 7, label: "Dom" },
];
const DEFAULT_BULK_ISO_WEEKDAYS = [1, 2, 3, 4, 5];

function analyticsStatusSummary(byStatus) {
  const source = byStatus || {};
  return [
    { key: "sin_revision", label: "Sin revisión", value: Number(source.sin_revision || 0), color: "#f59e0b" },
    { key: "revisado", label: "Revisado", value: Number(source.revisado || 0), color: "#10b981" },
    { key: "finalizada", label: "Finalizada", value: Number(source.finalizada || 0), color: "#2563eb" },
    { key: "no_presentada", label: "No presentada", value: Number(source.no_presentada || 0), color: "#64748b" },
    { key: "cancelado", label: "Cancelado", value: Number(source.cancelado || 0), color: "#ef4444" },
  ];
}

function getInitials(name) {
  const clean = (name || "").trim();
  if (!clean) return "?";
  const parts = clean.split(/\s+/).filter(Boolean);
  const first = parts[0]?.[0] || "";
  const last = parts.length > 1 ? parts[parts.length - 1]?.[0] || "" : "";
  return (first + last).toUpperCase();
}

function optimizeCloudinaryImage(url, width = 160) {
  const raw = String(url || "").trim();
  if (!raw || !raw.includes("res.cloudinary.com")) return raw;
  if (raw.includes("/upload/f_") || raw.includes("/upload/q_") || raw.includes("/upload/w_")) return raw;
  return raw.replace("/upload/", `/upload/f_auto,q_auto,w_${width},c_limit/`);
}

function getIsoWeekday(date) {
  const js = date.getDay();
  return js === 0 ? 7 : js;
}

function formatLongEsDate(date) {
  return date.toLocaleDateString("es-CO", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

function formatLongEsDateFromISO(isoDate) {
  if (!isoDate) return "";
  const [y, m, d] = String(isoDate).split("-").map(Number);
  if (!y || !m || !d) return isoDate;
  return formatLongEsDate(new Date(y, m - 1, d));
}

/** Evita enviar unload_team_id de otra bodega tras cambiar de bodega en el selector. */
function resolveUnloadTeamIdForWarehouse(teamId, teams, warehouseId) {
  if (teamId == null || teamId === "" || warehouseId == null || warehouseId === "") return "";
  const id = Number(teamId);
  const whId = Number(warehouseId);
  if (!Number.isFinite(id) || id < 1 || !Number.isFinite(whId) || whId < 1) return "";
  if (teams.some((t) => Number(t.id) === id && Number(t.warehouse_id) === whId)) return String(id);
  return "";
}

function formatTodayWindowsHint(dayIso, resolvedData, availability = null) {
  const franjas = buildSlotsFromFranjas(Array.isArray(resolvedData?.franjas) ? resolvedData.franjas : []);

  if (franjas.length === 0) {
    return `Hoy (${dayIso}) no tiene turnos configurados para agendar.`;
  }

  const ranges = Array.from(
    new Set(
      franjas.map((w) => {
        const duration =
          Number(w.duration_minutes) || slotDurationMinutes(w.start_local, w.end_local);
        return formatSlotLabel({
          start_local: w.start_local,
          end_local: w.end_local,
          duration_minutes: duration,
        });
      })
    )
  ).join(", ");
  const franjaLine = `Hoy (${dayIso}) los turnos habilitados son: ${ranges}.`;

  if (!availability) {
    return franjaLine;
  }

  const reason = String(availability.reason || "").trim();
  const message = String(availability.message || "").trim();
  const minHours = Number(availability.minimumNoticeHours) || 24;
  const times = Array.isArray(availability.times) ? availability.times : [];

  if (reason === "minimum_notice") {
    if (message) return `${franjaLine} ${message}`;
    return `${franjaLine} No puedes agendar para este día: hace falta al menos ${minHours} horas de anticipación antes de la hora de la cita.`;
  }

  if (times.length > 0) {
    return `${franjaLine} Puedes agendar hoy en: ${times.join(", ")}.`;
  }

  if (message) return `${franjaLine} ${message}`;

  return franjaLine;
}

function buildMonthCalendar(referenceDate, allowedDays) {
  const year = referenceDate.getFullYear();
  const month = referenceDate.getMonth();
  const first = new Date(year, month, 1);
  const last = new Date(year, month + 1, 0);
  const leading = getIsoWeekday(first) - 1; // lunes=1 -> 0
  const cells = [];
  for (let i = 0; i < leading; i += 1) {
    cells.push(null);
  }
  for (let day = 1; day <= last.getDate(); day += 1) {
    const d = new Date(year, month, day);
    const iso = getIsoWeekday(d);
    const dateISO = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    cells.push({
      day,
      dateISO,
      isoWeekday: iso,
      enabled: allowedDays.includes(iso),
      isToday: d.toDateString() === new Date().toDateString(),
      isPast: dateISO < todayISO(),
    });
  }
  return { year, month, cells };
}

/** `data-tour` estable para títulos de sección del menú (p. ej. Principal → `nav-section-principal`). */
function navSectionDataTourFromLabel(text) {
  const slug = String(text || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return slug ? `nav-section-${slug}` : "";
}

function getPasswordStrengthError(password) {
  const pwd = password || "";
  if (pwd.length < 8) return "La contraseña debe tener al menos 8 caracteres.";
  if (!/[a-z]/.test(pwd)) return "Debe incluir al menos una letra minúscula.";
  if (!/[A-Z]/.test(pwd)) return "Debe incluir al menos una letra mayúscula.";
  if (!/[0-9]/.test(pwd)) return "Debe incluir al menos un número.";
  if (!/[^A-Za-z0-9]/.test(pwd)) return "Debe incluir al menos un símbolo (ej.: !@#$).";
  return "";
}

function matchesWarehouseFilter(appointment, filterWarehouseId) {
  if (!filterWarehouseId) return true;
  return Number(appointment?.warehouse_id) === Number(filterWarehouseId);
}

function getFranjaValidationError(rows, context = "franja") {
  if (!Array.isArray(rows) || rows.length === 0) return `No hay ${context}s para guardar.`;
  const ordered = rows
    .map((r) => ({
      start_local: String(r?.start_local || ""),
      end_local: String(r?.end_local || ""),
    }))
    .sort((a, b) => a.start_local.localeCompare(b.start_local));
  for (let i = 0; i < ordered.length; i += 1) {
    const row = ordered[i];
    if (!row.start_local || !row.end_local) {
      return `La ${context} #${i + 1} está incompleta.`;
    }
    if (row.end_local <= row.start_local) {
      return `La ${context} #${i + 1} tiene hora fin menor o igual a la de inicio.`;
    }
    const duration = slotDurationMinutes(row.start_local, row.end_local);
    if (duration < 15) {
      return `La ${context} #${i + 1} debe durar al menos 15 minutos.`;
    }
    if (duration > 480) {
      return `La ${context} #${i + 1} no puede durar más de 480 minutos.`;
    }
    if (i > 0 && row.start_local < ordered[i - 1].end_local) {
      return `La ${context} #${i + 1} se solapa con la anterior (debe iniciar a las ${formatLocalTime12h(
        ordered[i - 1].end_local
      )} o después).`;
    }
  }
  return "";
}

export default function DashboardPage() {
  const { session, authReady, logout } = useAuth();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [appointments, setAppointments] = useState([]);
  const [logs, setLogs] = useState([]);
  const [roles, setRoles] = useState([]);
  const [internalUsers, setInternalUsers] = useState([]);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [toasts, setToasts] = useState([]);
  const [viewMode, setViewMode] = useState("list");
  const [viewPeriod, setViewPeriod] = useState(() => getDefaultPeriodIndex("today"));
  const [filterDay, setFilterDay] = useState(todayISO());
  const [filterMonth, setFilterMonth] = useState(new Date().getMonth() + 1);
  const [filterYear, setFilterYear] = useState(new Date().getFullYear());

  const [nuDoc, setNuDoc] = useState("");
  const [nuEmail, setNuEmail] = useState("");
  const [nuName, setNuName] = useState("");
  const [nuPass, setNuPass] = useState("");
  const [nuPassConfirm, setNuPassConfirm] = useState("");
  const [nuRoleId, setNuRoleId] = useState("");
  const [nuWarehouseIds, setNuWarehouseIds] = useState([]);
  const [editUserWarehouseIds, setEditUserWarehouseIds] = useState([]);
  const [staffNameFilter, setStaffNameFilter] = useState("");
  const [staffRoleFilter, setStaffRoleFilter] = useState("");
  const [showNuPass, setShowNuPass] = useState(false);
  const [showNuPassConfirm, setShowNuPassConfirm] = useState(false);
  const [teamMessage, setTeamMessage] = useState("");
  const [editingUserId, setEditingUserId] = useState("");
  const [editUserName, setEditUserName] = useState("");
  const [editUserEmail, setEditUserEmail] = useState("");
  const [editUserRoleId, setEditUserRoleId] = useState("");
  const [confirmDeleteUserId, setConfirmDeleteUserId] = useState("");
  const [providers, setProviders] = useState([]);
  const [providerFilter, setProviderFilter] = useState("");
  const [providerStatusFilter, setProviderStatusFilter] = useState("");
  const [providersMessage, setProvidersMessage] = useState("");
  const [editingProviderNit, setEditingProviderNit] = useState(null);
  const [editProviderCompany, setEditProviderCompany] = useState("");
  const [editProviderEmail, setEditProviderEmail] = useState("");
  const [editProviderContact, setEditProviderContact] = useState("");
  const [editProviderContactDoc, setEditProviderContactDoc] = useState("");
  const [editProviderDigit, setEditProviderDigit] = useState("");
  const [editProviderPassword, setEditProviderPassword] = useState("");
  const [confirmDeleteProviderNit, setConfirmDeleteProviderNit] = useState(null);
  const [confirmSuspendProvider, setConfirmSuspendProvider] = useState(null);
  const [suspendReason, setSuspendReason] = useState("");

  const [adminTab, setAdminTab] = useState("citas");
  const [logisticaTab, setLogisticaTab] = useState("citas");
  const [proveedorTab, setProveedorTab] = useState("inicio");
  const [windowsPack, setWindowsPack] = useState(null);
  const [todayWindowsHint, setTodayWindowsHint] = useState("");
  const [providerCalendarMonthOffset, setProviderCalendarMonthOffset] = useState(0);
  const [providerAvailableDays, setProviderAvailableDays] = useState([]);
  const [providerSelectedDay, setProviderSelectedDay] = useState(todayISO());
  const [providerSelectedSlots, setProviderSelectedSlots] = useState([]);
  const [providerSlotUnavailableMessage, setProviderSlotUnavailableMessage] = useState("");
  const [providerSlotUnavailableReason, setProviderSlotUnavailableReason] = useState("");
  const [providerMinimumNoticeHours, setProviderMinimumNoticeHours] = useState(24);
  const [providerDayAvailabilityLoading, setProviderDayAvailabilityLoading] = useState(false);
  const [providerCreateSubmitting, setProviderCreateSubmitting] = useState(false);
  const [providerDayAvailabilityError, setProviderDayAvailabilityError] = useState("");
  const [warehouses, setWarehouses] = useState([]);
  const [selectedWarehouseId, setSelectedWarehouseId] = useState(null);
  const [filterWarehouseId, setFilterWarehouseId] = useState("");
  const [providerListWarehouseFilter, setProviderListWarehouseFilter] = useState("");
  const [newWarehouseName, setNewWarehouseName] = useState("");
  const [newWarehouseAddress, setNewWarehouseAddress] = useState("");
  const [newWarehouseUnloadTeams, setNewWarehouseUnloadTeams] = useState(1);
  const [warehouseTeamNamesEditId, setWarehouseTeamNamesEditId] = useState(null);
  const [warehouseTeamNamesDraft, setWarehouseTeamNamesDraft] = useState([]);
  const [warehouseTeamNamesLoading, setWarehouseTeamNamesLoading] = useState(false);
  const [warehouseEquiposDraft, setWarehouseEquiposDraft] = useState({});
  const [warehouseConfigApplyingId, setWarehouseConfigApplyingId] = useState(null);
  const [warehouseTeamNamesBaseline, setWarehouseTeamNamesBaseline] = useState([]);
  const [warehouseRowError, setWarehouseRowError] = useState({});
  const [warehouseUnloadTeams, setWarehouseUnloadTeams] = useState([]);
  const [selectedWarehouseUnloadTeamId, setSelectedWarehouseUnloadTeamId] = useState(null);
  const [adminFranjaUnloadTeamId, setAdminFranjaUnloadTeamId] = useState("");
  const [providerTimeChoice, setProviderTimeChoice] = useState("");
  const [providerMaterialDescription, setProviderMaterialDescription] = useState("");
  const [providerAppointments, setProviderAppointments] = useState([]);
  const [providerCancelReasonById, setProviderCancelReasonById] = useState({});
  const [providerNotificationAppointment, setProviderNotificationAppointment] = useState(null);
  const [providerNotificationModalOpen, setProviderNotificationModalOpen] = useState(false);
  const [providerNotificationModalLoading, setProviderNotificationModalLoading] = useState(false);
  const [providerNotificationModalError, setProviderNotificationModalError] = useState("");
  const [providerNotificationRescheduleOpen, setProviderNotificationRescheduleOpen] = useState(false);
  const [reminders, setReminders] = useState([]);
  const [franjaRows, setFranjaRows] = useState([
    { start_local: "08:00", end_local: "11:00" },
    { start_local: "13:00", end_local: "16:00" },
  ]);
  const [specialDay, setSpecialDay] = useState(todayISO());
  const [specialFranjaRows, setSpecialFranjaRows] = useState([{ start_local: "08:00", end_local: "11:00" }]);
  const [specialDayMessage, setSpecialDayMessage] = useState("");
  const [specialDayCanEdit, setSpecialDayCanEdit] = useState(true);
  const [specialDayAppointmentsCount, setSpecialDayAppointmentsCount] = useState(0);
  const [bulkStartDay, setBulkStartDay] = useState(todayISO());
  const [bulkEndDay, setBulkEndDay] = useState(todayISO());
  const [bulkFranjaRows, setBulkFranjaRows] = useState([
    { start_local: "08:00", end_local: "11:00" },
    { start_local: "13:00", end_local: "16:00" },
  ]);
  const [bulkMessage, setBulkMessage] = useState("");
  const [bulkIsoWeekdays, setBulkIsoWeekdays] = useState(DEFAULT_BULK_ISO_WEEKDAYS);
  const [calendarOverrideDays, setCalendarOverrideDays] = useState([]);
  const [teamHasWeeklyFranjas, setTeamHasWeeklyFranjas] = useState(false);
  const [scheduledIsoWeekdays, setScheduledIsoWeekdays] = useState([]);
  const [unloadTeamsReadyWarehouseId, setUnloadTeamsReadyWarehouseId] = useState(null);

  const activeAdminFranjaTeamId = useMemo(
    () =>
      resolveUnloadTeamIdForWarehouse(
        adminFranjaUnloadTeamId,
        warehouseUnloadTeams,
        selectedWarehouseId
      ),
    [adminFranjaUnloadTeamId, warehouseUnloadTeams, selectedWarehouseId]
  );

  const activeProviderUnloadTeamId = useMemo(() => {
    const resolved = resolveUnloadTeamIdForWarehouse(
      selectedWarehouseUnloadTeamId,
      warehouseUnloadTeams,
      selectedWarehouseId
    );
    return resolved ? Number(resolved) : null;
  }, [selectedWarehouseUnloadTeamId, warehouseUnloadTeams, selectedWarehouseId]);

  const [calendarMonthOffset, setCalendarMonthOffset] = useState(0);
  const [analytics, setAnalytics] = useState(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const analyticsLoadSeqRef = useRef(0);
  const [auditActorId, setAuditActorId] = useState("");
  const [auditAppointmentId, setAuditAppointmentId] = useState("");
  const [auditWarehouseFilter, setAuditWarehouseFilter] = useState("");
  const [auditTextFilter, setAuditTextFilter] = useState("");
  const [auditRoleFilter, setAuditRoleFilter] = useState("");
  const [expandedAuditLogIds, setExpandedAuditLogIds] = useState([]);
  const [historyDateFilter, setHistoryDateFilter] = useState("");
  const [analyticsRange, setAnalyticsRange] = useState("today");
  const [analyticsPeriod, setAnalyticsPeriod] = useState(() => getDefaultPeriodIndex("today"));
  const [analyticsMonth, setAnalyticsMonth] = useState(new Date().getMonth() + 1);
  const [analyticsYear, setAnalyticsYear] = useState(new Date().getFullYear());
  const [analyticsDay, setAnalyticsDay] = useState(() => todayISOInTimeZone());
  const [citasRange, setCitasRange] = useState("today");
  const [citasDay, setCitasDay] = useState(() => todayISO());
  const [citasPeriod, setCitasPeriod] = useState(() => getDefaultPeriodIndex("today"));
  const [citasMonth, setCitasMonth] = useState(() => new Date().getMonth() + 1);
  const [citasYear, setCitasYear] = useState(() => new Date().getFullYear());
  const [reviewRange, setReviewRange] = useState("today");
  const [reviewPeriod, setReviewPeriod] = useState(() => getDefaultPeriodIndex("today"));
  const [reviewMonth, setReviewMonth] = useState(() => new Date().getMonth() + 1);
  const [reviewYear, setReviewYear] = useState(() => new Date().getFullYear());
  const [reviewDay, setReviewDay] = useState(() => todayISOInTimeZone());
  const [reviewReferenceDate, setReviewReferenceDate] = useState(() => new Date());
  const [revisionOpenAppointmentId, setRevisionOpenAppointmentId] = useState(null);
  const [revisionPinnedAppointment, setRevisionPinnedAppointment] = useState(null);
  const [profileData, setProfileData] = useState(null);
  const [profileFullName, setProfileFullName] = useState("");
  const [profileEmail, setProfileEmail] = useState("");
  const [profileCurrentPassword, setProfileCurrentPassword] = useState("");
  const [profileNewPassword, setProfileNewPassword] = useState("");
  const [profileConfirmPassword, setProfileConfirmPassword] = useState("");
  const [profilePhotoFile, setProfilePhotoFile] = useState(null);
  const [profilePhotoMessage, setProfilePhotoMessage] = useState("");
  const profilePhotoInputRef = useRef(null);
  const selectedDaySectionRef = useRef(null);
  const initialBootstrapDoneRef = useRef(false);
  const providerDayAvailabilitySeqRef = useRef(0);
  const [showProfileCurrentPassword, setShowProfileCurrentPassword] = useState(false);
  const [showProfileNewPassword, setShowProfileNewPassword] = useState(false);
  const [showProfileConfirmPassword, setShowProfileConfirmPassword] = useState(false);
  /** Evita translate animado en móvil durante la guía modal (drawer + animación). */
  const [panelTourLayout, setPanelTourLayout] = useState(false);
  const [panelGuidedOpen, setPanelGuidedOpen] = useState(false);
  const [panelGuidedIndex, setPanelGuidedIndex] = useState(0);
  const [panelGuidedSteps, setPanelGuidedSteps] = useState([]);

  /** Ítem del menú a resaltar: derivado del paso (evita desfase con el estado al pulsar Siguiente). */
  const guidedTourExpectedNavId = useMemo(() => {
    if (!panelGuidedOpen) return "";
    const step = panelGuidedSteps[panelGuidedIndex];
    if (!step?.moduleTarget) return "";
    return MODULE_TO_NAV_TOUR_ID[step.moduleTarget] || "";
  }, [panelGuidedOpen, panelGuidedIndex, panelGuidedSteps]);

  const isGlobalAdmin = session?.role === "Admin";
  const isWarehouseAdmin = session?.role === "AdminBodega";
  const isAdmin = isGlobalAdmin;
  const isAdminPanel = isGlobalAdmin || isWarehouseAdmin;
  const isLogistica = session?.role === "Logistica";
  const isProveedor = session?.role === "Proveedor";

  /** Recarga calendario/franjas solo cuando cambia el muelle relevante al rol actual. */
  const warehouseSchedulingTeamKey = isProveedor ? activeProviderUnloadTeamId : activeAdminFranjaTeamId;

  useEffect(() => {
    const mq = window.matchMedia("(min-width: 1024px)");
    const applyScrollLock = () => {
      if (mq.matches) {
        document.documentElement.style.overflow = "hidden";
        document.body.style.overflow = "hidden";
      } else {
        document.documentElement.style.overflow = "";
        document.body.style.overflow = "";
      }
    };

    applyScrollLock();
    mq.addEventListener("change", applyScrollLock);
    document.body.classList.add("dashboard-panel-active");
    return () => {
      mq.removeEventListener("change", applyScrollLock);
      document.documentElement.style.overflow = "";
      document.body.style.overflow = "";
      document.body.classList.remove("dashboard-panel-active");
    };
  }, []);

  const isStaff = isLogistica || isAdminPanel;
  /** Auditoría global, por bodegas asignadas (AdminBodega) o historial propio (Logística). */
  const canLoadAuditLogs = isAdmin || isLogistica || isWarehouseAdmin;
  const showWarehouseAuditPanel = isWarehouseAdmin && adminTab === "auditoria";
  const showGlobalAuditPanel = isGlobalAdmin && adminTab === "auditoria";
  const adminNavEntries = isWarehouseAdmin ? ADMIN_BODEGA_NAV : ADMIN_NAV;

  const internalRolesOnly = useMemo(() => {
    const wanted = ["Admin", "Logistica", "AdminBodega"];
    const seen = new Set();
    const list = [];
    for (const r of roles) {
      if (!wanted.includes(r.name) || seen.has(r.name)) continue;
      seen.add(r.name);
      list.push(r);
    }
    return list;
  }, [roles]);
  const staffUsersOnly = internalUsers.filter((u) =>
    ["Admin", "Logistica", "AdminBodega"].includes(u.role_name)
  );
  const nuRoleName = internalRolesOnly.find((r) => String(r.id) === String(nuRoleId))?.name || "";
  const editRoleName =
    internalRolesOnly.find((r) => String(r.id) === String(editUserRoleId))?.name || "";
  const filteredProviders = useMemo(() => {
    const q = providerFilter.trim().toLowerCase();
    const nitQ = providerFilter.replace(/\D/g, "");
    return providers.filter((p) => {
      const matchesStatus = providerStatusFilter.length === 0 || p.status === providerStatusFilter;
      const matchesText =
        q.length === 0 ||
        (p.company_name || "").toLowerCase().includes(q) ||
        (p.company_email || "").toLowerCase().includes(q) ||
        (p.contact_name || "").toLowerCase().includes(q) ||
        (nitQ.length > 0 && String(p.nit || "").includes(nitQ));
      return matchesStatus && matchesText;
    });
  }, [providers, providerFilter, providerStatusFilter]);

  const providerStats = useMemo(() => {
    const total = providers.length;
    const activos = providers.filter((p) => p.status === "activo").length;
    const suspendidos = providers.filter((p) => p.status === "suspendido").length;
    return { total, activos, suspendidos };
  }, [providers]);

  const filteredStaffUsers = useMemo(() => {
    const nameQ = staffNameFilter.trim().toLowerCase();
    const docQ = staffNameFilter.replace(/\D/g, "");
    return staffUsersOnly.filter((u) => {
      const matchesName =
        nameQ.length === 0 ||
        u.full_name.toLowerCase().includes(nameQ) ||
        u.email.toLowerCase().includes(nameQ) ||
        (docQ.length > 0 && String(u.document_id || "").replace(/\D/g, "").includes(docQ));
      const matchesRole = staffRoleFilter.length === 0 || u.role_name === staffRoleFilter;
      return matchesName && matchesRole;
    });
  }, [staffUsersOnly, staffNameFilter, staffRoleFilter]);

  const activeNavLabel = useMemo(() => {
    if (isProveedor) {
      if (proveedorTab === "configuraciones") return "Configuraciones";
      if (proveedorTab === "historial") return "Historial";
      if (proveedorTab === "mis_citas") return "Mis citas";
      return "Inicio";
    }
    if (isLogistica) {
      if (logisticaTab === "citas") return "Citas";
      if (logisticaTab === "buscar_citas") return "Buscar citas";
      if (logisticaTab === "revision_citas") return "Revision de citas";
      if (logisticaTab === "configuraciones") return "Configuraciones";
      return "Historial";
    }
    const item = adminNavEntries.find((x) => x.type === "item" && x.id === adminTab);
    return item?.label || "Panel";
  }, [isProveedor, proveedorTab, isLogistica, logisticaTab, adminTab, adminNavEntries]);

  const closePanelGuidedTour = useCallback(() => {
    setPanelGuidedOpen(false);
    setPanelTourLayout(false);
    if (isNarrowPanelTourViewport()) setMobileNavOpen(false);
  }, []);

  /** Cambia cuando el DOM del panel (pestaña, drawer, ítem del paso) se actualiza: el manual reaplica el spotlight. */
  const panelTourSpotlightLayoutKey = useMemo(() => {
    if (!panelGuidedOpen) return "";
    return [adminTab, logisticaTab, proveedorTab, guidedTourExpectedNavId, mobileNavOpen ? 1 : 0].join("|");
  }, [panelGuidedOpen, adminTab, logisticaTab, proveedorTab, guidedTourExpectedNavId, mobileNavOpen]);

  useLayoutEffect(() => {
    if (!panelGuidedOpen) return;
    const step = panelGuidedSteps[panelGuidedIndex];
    if (!step) return;

    const narrow = isNarrowPanelTourViewport();
    const navId = step.moduleTarget ? MODULE_TO_NAV_TOUR_ID[step.moduleTarget] || "" : "";

    if (narrow) {
      if (step.sidebarMobile === "open") setMobileNavOpen(true);
      else if (step.sidebarMobile === "close") setMobileNavOpen(false);
    }
    if (step.moduleTarget) {
      if (isAdminPanel) setAdminTab(step.moduleTarget);
      if (isLogistica) setLogisticaTab(step.moduleTarget);
      if (isProveedor) setProveedorTab(step.moduleTarget);
    }

    window.requestAnimationFrame(() => {
      if (!navId) return;
      const navItem = document.querySelector(
        `${TOUR_DASHBOARD_SIDEBAR_SELECTOR} [data-tour="${navId}"]`
      );
      const menuContainer = navItem?.closest('[data-tour="sidebar"]');
      if (menuContainer && navItem) scrollDashboardSidebarNavItemIntoView(menuContainer, navItem);
    });

    if (step.scrollMainTop) {
      const mainEl = document.getElementById("dashboard-main-content");
      if (mainEl) mainEl.scrollTo({ top: 0, behavior: "auto" });
    }
  }, [panelGuidedOpen, panelGuidedIndex, panelGuidedSteps, isAdmin, isLogistica, isProveedor]);

  const startManualTour = useCallback(() => {
    const narrow = isNarrowPanelTourViewport();
    if (narrow) {
      setPanelTourLayout(true);
      setMobileNavOpen(true);
    }
    if (isAdminPanel) setAdminTab("citas");
    if (isLogistica) setLogisticaTab("citas");
    if (isProveedor) setProveedorTab("inicio");

    const bootDelayMs = manualTourBootDelayMs();
    window.setTimeout(async () => {
      const { getPanelGuidedSteps } = await import("../guidedTour/panelSteps");
      const steps = getPanelGuidedSteps(isGlobalAdmin, isWarehouseAdmin, isLogistica, isProveedor);
      setPanelGuidedSteps(steps);
      setPanelGuidedIndex(0);
      if (!narrow) setPanelTourLayout(true);
      setPanelGuidedOpen(true);
    }, bootDelayMs);
  }, [isAdmin, isLogistica, isProveedor]);

  const loadAppointments = useCallback(async () => {
    if (!session || !authReady || !isStaff) return;
    const isRevisionTabActive =
      (isAdminPanel && adminTab === "revision_citas") || (isLogistica && logisticaTab === "revision_citas");
    const buildParams = (modeOverride) => {
      const params = new URLSearchParams();
      params.set("page", "1");
      params.set("page_size", isRevisionTabActive ? "200" : "100");

      if (isRevisionTabActive) {
        const apiMode = reviewRange === "today" ? "day" : reviewRange;
        params.set("mode", apiMode);
        if (apiMode === "day") {
          params.set("day", reviewDay || todayISOInTimeZone());
        }
        if (apiMode === "month") {
          params.set("month", String(reviewMonth));
          params.set("year", String(reviewYear));
        }
        if (rangeNeedsPeriodSelector(reviewRange) && reviewPeriod != null) {
          params.set("period", String(reviewPeriod));
        }
        params.append("status", "sin_revision");
        params.append("status", "revisado");
      } else {
        const effectiveMode = modeOverride ?? (viewMode === "list" ? "week" : viewMode);
        params.set("mode", effectiveMode);
        if (effectiveMode === "day" && filterDay) {
          params.set("day", filterDay);
        }
        if (effectiveMode === "month") {
          params.set("month", String(filterMonth));
          params.set("year", String(filterYear));
        }
        if (rangeNeedsPeriodSelector(effectiveMode) && viewPeriod != null) {
          params.set("period", String(viewPeriod));
        }
      }

      if (filterWarehouseId) {
        params.set("warehouse_id", String(filterWarehouseId));
      }
      return params;
    };

    const requestMode = isRevisionTabActive
      ? reviewRange === "today"
        ? "day"
        : reviewRange
      : viewMode;

    try {
      const response = await api.get(`${API_PREFIX}/crud/appointments?${buildParams().toString()}`);
      const payload = parseApiResponse(response);
      if (!payload.success) {
        throw new Error(payload.message || "No se pudieron cargar las citas.");
      }
      const inner = payload.data;
      setAppointments(Array.isArray(inner) ? inner : inner?.items ?? []);
    } catch (err) {
      const status = err?.response?.status;
      if (status === 401 || status === 403) {
        throw err;
      }
      if (requestMode === "list") {
        throw err;
      }
      // Fallback solo si el filtro activo falla por datos incompatibles, no por sesión.
      const response = await api.get(`${API_PREFIX}/crud/appointments?${buildParams("list").toString()}`);
      const payload = parseApiResponse(response);
      if (!payload.success) {
        throw new Error(payload.message || "No se pudieron cargar las citas.");
      }
      const inner = payload.data;
      setAppointments(Array.isArray(inner) ? inner : inner?.items ?? []);
    }
  }, [
    session,
    authReady,
    viewMode,
    viewPeriod,
    filterDay,
    filterMonth,
    filterYear,
    filterWarehouseId,
    reviewRange,
    reviewPeriod,
    reviewMonth,
    reviewYear,
    reviewDay,
    reviewReferenceDate,
    isAdmin,
    isLogistica,
    adminTab,
    logisticaTab,
  ]);

  const loadLogs = useCallback(async () => {
    if (!session || !canLoadAuditLogs) return;
    const params = new URLSearchParams();
    params.set("page", "1");
    params.set("page_size", "200");
    if (auditActorId.trim()) {
      params.set("actor_id", auditActorId.trim());
    }
    if (auditAppointmentId.trim()) {
      params.set("appointment_id", auditAppointmentId.trim());
    }
    if (isWarehouseAdmin && auditWarehouseFilter) {
      params.set("warehouse_id", String(auditWarehouseFilter));
    }
    const response = await api.get(`${API_PREFIX}/crud/change-logs?${params.toString()}`);
    const payload = parseApiResponse(response);
    if (!payload.success) {
      throw new Error(payload.message);
    }
    const inner = payload.data;
    setLogs(inner?.items ?? (Array.isArray(inner) ? inner : []));
  }, [
    session,
    auditActorId,
    auditAppointmentId,
    auditWarehouseFilter,
    canLoadAuditLogs,
    isWarehouseAdmin,
  ]);

  /** Tras cambiar una cita no debe fallar la acción si solo falla el refresco del historial. */
  const refreshAuditLogsBestEffort = useCallback(async () => {
    if (!canLoadAuditLogs) return;
    try {
      await loadLogs();
    } catch {
      /* El historial se puede ver en la pestaña Auditoría. */
    }
  }, [canLoadAuditLogs, loadLogs]);

  const loadReminders = useCallback(async () => {
    if (!session || !isStaff) return;
    const response = await api.get(`${API_PREFIX}/crud/reminders?page=1&page_size=25`);
    const payload = parseApiResponse(response);
    if (!payload.success) {
      throw new Error(payload.message || "No se pudieron cargar los recordatorios.");
    }
    const inner = payload.data;
    setReminders(inner?.items ?? []);
  }, [session, isStaff]);

  const loadRoles = useCallback(async () => {
    if (!session || !isAdmin) return;
    const response = await api.get(`${API_PREFIX}/crud/roles`);
    const payload = parseApiResponse(response);
    if (!payload.success) {
      throw new Error(payload.message);
    }
    setRoles(payload.data || []);
  }, [session, isAdmin]);

  const loadInternalUsers = useCallback(async () => {
    if (!session || !authReady || !isAdmin) return;
    const response = await api.get(`${API_PREFIX}/crud/users`);
    const payload = parseApiResponse(response);
    if (!payload.success) {
      throw new Error(payload.message);
    }
    setInternalUsers(payload.data || []);
  }, [session, authReady, isAdmin]);

  const loadProviders = useCallback(async () => {
    if (!session || !authReady || !isAdmin) return;
    const response = await api.get(`${API_PREFIX}/crud/providers`);
    const payload = parseApiResponse(response);
    if (!payload.success) {
      throw new Error(payload.message);
    }
    const raw = payload.data;
    const items = Array.isArray(raw?.items) ? raw.items : Array.isArray(raw) ? raw : [];
    setProviders(items);
  }, [session, authReady, isAdmin]);

  const applyWarehouseList = useCallback((items) => {
    const list = Array.isArray(items) ? items : [];
    setWarehouses(list);
    setSelectedWarehouseId((prev) => {
      if (prev && list.some((w) => w.id === prev)) return prev;
      return list[0]?.id ?? null;
    });
  }, []);

  const loadWarehouses = useCallback(async () => {
    if (!session) return;
    try {
      const response = await api.get(`${API_PREFIX}/crud/warehouses`);
      const payload = parseApiResponse(response);
      if (!payload.success) {
        throw new Error(payload.message);
      }
      applyWarehouseList(payload.data);
    } catch (err) {
      if (isApiRouteMissing(err)) {
        applyWarehouseList([]);
        return;
      }
      throw err;
    }
  }, [session, applyWarehouseList]);

  const loadWindows = useCallback(async () => {
    if (!session || !selectedWarehouseId) return;
    const whId = Number(selectedWarehouseId);
    if (!isProveedor) {
      const params = new URLSearchParams({ warehouse_id: String(whId) });
      if (activeAdminFranjaTeamId) {
        params.set("unload_team_id", activeAdminFranjaTeamId);
      }
      const response = await api.get(`${API_PREFIX}/crud/appointment-franjas?${params.toString()}`);
      const payload = parseApiResponse(response);
      if (!payload.success) {
        throw new Error(payload.message);
      }
      setWindowsPack(payload.data || null);
      const f = payload.data?.franjas;
      if (Array.isArray(f) && f.length > 0) {
        setFranjaRows(f.map((w) => ({ start_local: w.start_local, end_local: w.end_local })));
        setTeamHasWeeklyFranjas(true);
      } else {
        setFranjaRows([]);
        if (activeAdminFranjaTeamId) {
          setTeamHasWeeklyFranjas(false);
        }
      }
    }
    const today = todayISO();
    const resolvedParams = new URLSearchParams({
      day: today,
      warehouse_id: String(selectedWarehouseId),
    });
    const hintUnloadTeamId = isProveedor
      ? activeProviderUnloadTeamId
      : activeAdminFranjaTeamId
        ? Number(activeAdminFranjaTeamId)
        : null;
    if (hintUnloadTeamId) {
      resolvedParams.set("unload_team_id", String(hintUnloadTeamId));
    }
    const resolvedResponse = await api.get(
      `${API_PREFIX}/crud/appointment-franjas/resolved?${resolvedParams.toString()}`
    );
    const resolvedPayload = parseApiResponse(resolvedResponse);
    let availability = null;
    if (isProveedor && activeProviderUnloadTeamId) {
      try {
        const availabilityResponse = await api.get(
          `${API_PREFIX}/appointments/available-slots?day=${today}&warehouse_id=${selectedWarehouseId}&unload_team_id=${activeProviderUnloadTeamId}`
        );
        const sourceData = unwrapProviderDayAvailability(availabilityResponse);
        const slots = normalizeAvailableSlots(sourceData);
        availability = {
          slots,
          times: slots.map((s) => slotKey(s)),
          reason: String(sourceData?.unavailable_reason || "").trim(),
          message: String(sourceData?.unavailable_message || "").trim(),
          minimumNoticeHours: Number(sourceData?.minimum_notice_hours || 24),
        };
      } catch {
        availability = null;
      }
    }
    if (resolvedPayload.success) {
      setTodayWindowsHint(formatTodayWindowsHint(today, resolvedPayload.data || null, availability));
      if (isProveedor) {
        const tz = resolvedPayload.data?.timezone || DEFAULT_BUSINESS_TZ;
        setWindowsPack((prev) => ({ ...(prev && typeof prev === "object" ? prev : {}), warehouse_id: whId, timezone: tz }));
      }
    } else {
      setTodayWindowsHint("");
    }
  }, [session, isProveedor, selectedWarehouseId, warehouseSchedulingTeamKey]);

  const loadSpecialDayWindows = useCallback(
    async (day) => {
      if (!session || !isAdminPanel || !day || !selectedWarehouseId) return;
      const params = new URLSearchParams({
        day: String(day),
        warehouse_id: String(selectedWarehouseId),
      });
      if (activeAdminFranjaTeamId) {
        params.set("unload_team_id", activeAdminFranjaTeamId);
      }
      const response = await api.get(
        `${API_PREFIX}/crud/appointment-franjas/fecha?${params.toString()}`
      );
      const payload = parseApiResponse(response);
      if (!payload.success) {
        throw new Error(payload.message);
      }
      const f = payload.data?.franjas;
      setSpecialDayCanEdit(Boolean(payload.data?.can_edit));
      setSpecialDayAppointmentsCount(Number(payload.data?.appointments_count || 0));
      if (Array.isArray(f) && f.length > 0) {
        setSpecialFranjaRows(f.map((w) => ({ start_local: w.start_local, end_local: w.end_local })));
      } else {
        setSpecialFranjaRows([]);
      }
    },
    [session, isAdmin, selectedWarehouseId, activeAdminFranjaTeamId]
  );

  useEffect(() => {
    if (!isAdminPanel || adminTab !== "horarios" || !specialDay) return;
    void loadSpecialDayWindows(specialDay);
  }, [isAdminPanel, adminTab, specialDay, activeAdminFranjaTeamId, loadSpecialDayWindows]);

  const loadProviderAppointments = useCallback(async () => {
    if (!session || !isProveedor) return [];
    const response = await api.get(`${API_PREFIX}/appointments?mode=list`);
    const payload = parseApiResponse(response);
    const raw = payload.success ? payload.data : response?.data;
    let items = [];
    if (raw && typeof raw === "object" && !Array.isArray(raw) && Array.isArray(raw.items)) {
      items = raw.items;
    } else if (Array.isArray(raw)) {
      items = raw;
    } else if (!payload.success) {
      throw new Error(payload.message || "No se pudieron cargar tus citas.");
    } else {
      const inner = payload.data;
      items = Array.isArray(inner) ? inner : inner?.items ?? [];
    }
    setProviderAppointments(items);
    setError("");
    return items;
  }, [session, isProveedor]);

  const loadWarehouseUnloadTeams = useCallback(async () => {
    if (!session || !selectedWarehouseId) {
      setWarehouseUnloadTeams([]);
      setSelectedWarehouseUnloadTeamId(null);
      return;
    }
    const whId = Number(selectedWarehouseId);
    const configuredMax = Math.max(
      1,
      Number(warehouses.find((w) => Number(w.id) === whId)?.unload_teams) || 1
    );
    try {
      const response = await api.get(
        `${API_PREFIX}/appointments/unload-teams?warehouse_id=${whId}`
      );
      const payload = parseApiResponse(response);
      const raw = Array.isArray(payload.data) ? payload.data : [];
      const teams = raw
        .filter((t) => Number(t.warehouse_id) === whId)
        .sort((a, b) => Number(a.sort_order ?? 0) - Number(b.sort_order ?? 0) || Number(a.id) - Number(b.id))
        .slice(0, configuredMax);
      setWarehouseUnloadTeams(teams);
      setUnloadTeamsReadyWarehouseId(whId);
      setSelectedWarehouseUnloadTeamId((prev) => {
        if (prev && teams.some((t) => Number(t.id) === Number(prev))) return prev;
        return teams.length === 1 ? teams[0]?.id ?? null : null;
      });
      if (!isProveedor) {
        setAdminFranjaUnloadTeamId((prev) => {
          if (prev && teams.some((t) => String(t.id) === String(prev))) return prev;
          return teams[0]?.id ? String(teams[0].id) : "";
        });
      }
    } catch {
      setWarehouseUnloadTeams([]);
      setSelectedWarehouseUnloadTeamId(null);
      setUnloadTeamsReadyWarehouseId(null);
    }
  }, [session, selectedWarehouseId, warehouses, isProveedor]);

  const fetchProviderDayAvailability = useCallback(
    async (dayIso, excludeAppointmentId = null, overrideUnloadTeamId = null) => {
      const teamId = overrideUnloadTeamId ?? activeProviderUnloadTeamId;
      if (!session || !isProveedor || !dayIso || !selectedWarehouseId || !teamId) {
        return { slots: [], times: [], reason: "", message: "", minimumNoticeHours: 24 };
      }
      let url = `${API_PREFIX}/appointments/available-slots?day=${dayIso}&warehouse_id=${selectedWarehouseId}&unload_team_id=${teamId}`;
      if (excludeAppointmentId != null) {
        url += `&exclude_appointment_id=${excludeAppointmentId}`;
      }
      const response = await api.get(url);
      const sourceData = unwrapProviderDayAvailability(response);
      const slots = normalizeAvailableSlots(sourceData);
      const times = slots.map((s) => slotKey(s));
      return {
        slots,
        times,
        reason: String(sourceData?.unavailable_reason || "").trim(),
        message: String(sourceData?.unavailable_message || "").trim(),
        minimumNoticeHours: Number(sourceData?.minimum_notice_hours || 24),
      };
    },
    [session, isProveedor, selectedWarehouseId, activeProviderUnloadTeamId]
  );

  useEffect(() => {
    setUnloadTeamsReadyWarehouseId(null);
    setWarehouseUnloadTeams([]);
    setSelectedWarehouseUnloadTeamId(null);
    setAdminFranjaUnloadTeamId("");
    setTeamHasWeeklyFranjas(false);
    setCalendarOverrideDays([]);
    void loadWarehouseUnloadTeams();
  }, [selectedWarehouseId, loadWarehouseUnloadTeams]);

  useEffect(() => {
    if (!isProveedor || warehouseUnloadTeams.length !== 1 || !providerSelectedDay) return;
    const only = warehouseUnloadTeams[0];
    if (only && !selectedWarehouseUnloadTeamId) {
      setSelectedWarehouseUnloadTeamId(only.id);
    }
  }, [isProveedor, warehouseUnloadTeams, providerSelectedDay, selectedWarehouseUnloadTeamId]);

  const resetProviderSlotSelection = useCallback(() => {
    setProviderSelectedSlots([]);
    setProviderTimeChoice("");
    setProviderSlotUnavailableReason("");
    setProviderSlotUnavailableMessage("");
    setProviderDayAvailabilityError("");
  }, []);

  const loadProviderDayAvailability = useCallback(
    async (dayIso) => {
      if (!session || !isProveedor || !dayIso) return;
      const requestSeq = ++providerDayAvailabilitySeqRef.current;
      setProviderDayAvailabilityLoading(true);
      setProviderDayAvailabilityError("");
      setProviderSlotUnavailableMessage("");
      setProviderSlotUnavailableReason("");
      setProviderSelectedSlots([]);
      setProviderTimeChoice("");
      try {
        const availability = await fetchProviderDayAvailability(dayIso);
        if (requestSeq !== providerDayAvailabilitySeqRef.current) return;
        setProviderSelectedSlots(availability.slots);
        setProviderMinimumNoticeHours(availability.minimumNoticeHours);
        setProviderSlotUnavailableReason(availability.times.length === 0 ? availability.reason : "");
        setProviderSlotUnavailableMessage(availability.times.length === 0 ? availability.message : "");
        setProviderTimeChoice((prev) =>
          availability.times.includes(prev) ? prev : availability.times[0] || ""
        );
        setError("");
      } catch (err) {
        if (requestSeq !== providerDayAvailabilitySeqRef.current) return;
        resetProviderSlotSelection();
        setProviderDayAvailabilityError(parseApiError(err));
      } finally {
        if (requestSeq === providerDayAvailabilitySeqRef.current) {
          setProviderDayAvailabilityLoading(false);
        }
      }
    },
    [session, isProveedor, fetchProviderDayAvailability, resetProviderSlotSelection]
  );

  const loadProviderMonthAvailability = useCallback(
    async (targetDate) => {
      if (!session || !isProveedor || !targetDate || !selectedWarehouseId) return;
      if (!activeProviderUnloadTeamId) {
        setProviderAvailableDays([]);
        return;
      }
      const year = targetDate.getFullYear();
      const month = targetDate.getMonth() + 1;
      const params = new URLSearchParams({
        year: String(year),
        month: String(month),
        warehouse_id: String(selectedWarehouseId),
        unload_team_id: String(activeProviderUnloadTeamId),
      });
      const response = await api.get(
        `${API_PREFIX}/crud/appointment-franjas/fecha/resumen?${params.toString()}`
      );
      const payload = parseApiResponse(response);
      if (!payload.success) {
        throw new Error(payload.message);
      }
      const today = todayISO();
      const openDays = Array.isArray(payload.data?.open_days) ? payload.data.open_days : [];
      setProviderAvailableDays(openDays.filter((d) => String(d) >= today));
    },
    [session, isProveedor, selectedWarehouseId, activeProviderUnloadTeamId]
  );

  const loadCalendarOverrideSummary = useCallback(
    async (targetDate) => {
      if (!session || !isAdminPanel || !targetDate || !selectedWarehouseId) return;
      const year = targetDate.getFullYear();
      const month = targetDate.getMonth() + 1;
      const params = new URLSearchParams({
        year: String(year),
        month: String(month),
        warehouse_id: String(selectedWarehouseId),
      });
      if (activeAdminFranjaTeamId) {
        params.set("unload_team_id", activeAdminFranjaTeamId);
      }
      const response = await api.get(
        `${API_PREFIX}/crud/appointment-franjas/fecha/resumen?${params.toString()}`
      );
      const payload = parseApiResponse(response);
      if (!payload.success) {
        throw new Error(payload.message);
      }
      setCalendarOverrideDays(
        Array.isArray(payload.data?.override_days) ? payload.data.override_days : []
      );
      setTeamHasWeeklyFranjas(Boolean(payload.data?.has_weekly_franjas));
      setScheduledIsoWeekdays(
        Array.isArray(payload.data?.scheduled_iso_weekdays) ? payload.data.scheduled_iso_weekdays : []
      );
    },
    [session, isAdminPanel, selectedWarehouseId, activeAdminFranjaTeamId]
  );

  const loadAnalytics = useCallback(async () => {
    if (!session || !isAdmin) return;
    const seq = ++analyticsLoadSeqRef.current;
    const range = analyticsRange;
    const dayIso = range === "today" ? analyticsDay || todayISOInTimeZone() : null;
    const warehouseId = filterWarehouseId;
    setAnalyticsLoading(true);
    try {
      const params = new URLSearchParams({ range });
      if (rangeNeedsPeriodSelector(range) && analyticsPeriod != null) {
        params.set("period", String(analyticsPeriod));
      }
      if (range === "month") {
        params.set("month", String(analyticsMonth));
        params.set("year", String(analyticsYear));
      }
      if (range === "today" && dayIso) {
        params.set("day", dayIso);
      }
      if (warehouseId) {
        params.set("warehouse_id", String(warehouseId));
      }
      const response = await api.get(`${API_PREFIX}/crud/analytics/summary?${params.toString()}`);
      if (seq !== analyticsLoadSeqRef.current) return;
      const payload = parseApiResponse(response);
      if (!payload.success) {
        throw new Error(payload.message);
      }
      let data = payload.data && typeof payload.data === "object" ? { ...payload.data } : {};
      if (range === "today" && dayIso && Number(data.total_citas || 0) === 0 && appointments.length > 0) {
        const fallback = summarizeAppointmentsByLocalDay(appointments, dayIso, warehouseId);
        if (fallback.total_citas > 0) {
          data = { ...data, ...fallback };
        }
      }
      setAnalytics(data);
    } finally {
      if (seq === analyticsLoadSeqRef.current) {
        setAnalyticsLoading(false);
      }
    }
  }, [
    session,
    isAdmin,
    analyticsRange,
    analyticsPeriod,
    analyticsMonth,
    analyticsYear,
    analyticsDay,
    filterWarehouseId,
    appointments,
  ]);

  const loadProfile = useCallback(async () => {
    if (!session) return;
    const response = await api.get(`${API_PREFIX}/crud/profile/me`);
    const payload = parseApiResponse(response);
    if (!payload.success) {
      throw new Error(payload.message);
    }
    const data = payload.data || null;
    setProfileData(data);
    setProfileFullName(data?.full_name || "");
    setProfileEmail(data?.email || "");
  }, [session]);

  const dismissToast = useCallback((id) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const pushToast = useCallback((message, type = "error") => {
    if (!message) return;
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    setToasts((prev) => {
      if (prev.some((toast) => toast.message === message && toast.type === type)) return prev;
      return [...prev, { id, message, type }];
    });
    setTimeout(() => {
      setToasts((prev) => prev.filter((toast) => toast.id !== id));
    }, TOAST_AUTO_DISMISS_MS);
  }, []);

  const onExportStaffXlsx = useCallback(async () => {
    const params = new URLSearchParams();
    params.set("mode", viewMode);
    if (viewMode === "day" && filterDay) params.set("day", filterDay);
    if (viewMode === "month") {
      params.set("month", String(filterMonth));
      params.set("year", String(filterYear));
    }
    if (rangeNeedsPeriodSelector(viewMode) && viewPeriod != null) {
      params.set("period", String(viewPeriod));
    }
    if (filterWarehouseId) {
      params.set("warehouse_id", String(filterWarehouseId));
    }
    try {
      const res = await api.get(`${API_PREFIX}/crud/appointments/export.xlsx?${params.toString()}`, {
        responseType: "blob",
      });
      const blob = new Blob([res.data], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `citas_${viewMode}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      pushToast("Archivo Excel descargado.", "success");
    } catch (err) {
      pushToast(parseApiError(err), "error");
    }
  }, [viewMode, viewPeriod, filterDay, filterMonth, filterYear, filterWarehouseId, pushToast]);

  useEffect(() => {
    if (!error) return;
    pushToast(error, "error");
    setError("");
  }, [error, pushToast]);

  useEffect(() => {
    if (!success) return;
    pushToast(success, "success");
    setSuccess("");
  }, [success, pushToast]);

  useEffect(() => {
    if (!session || !authReady) return;
    const flash = consumeWarehouseSaveFlash();
    if (flash) pushToast(flash, "success");
  }, [session, authReady, pushToast]);

  useEffect(() => {
    if (!session || !authReady) {
      initialBootstrapDoneRef.current = false;
      return;
    }
    if (initialBootstrapDoneRef.current) return;
    initialBootstrapDoneRef.current = true;
    const run = async () => {
      setError("");
      try {
        const tasks = [];
        if (isStaff) tasks.push(loadAppointments());
        if (isAdmin) {
          tasks.push(loadRoles());
          tasks.push(loadInternalUsers());
          tasks.push(loadProviders());
        }
        if (isStaff || isProveedor) tasks.push(loadWarehouses());
        if (isProveedor) tasks.push(loadProviderAppointments());
        const results = await Promise.allSettled(tasks);
        const failed = results.find((r) => r.status === "rejected");
        if (failed) {
          throw failed.reason;
        }
      } catch (err) {
        setError(parseApiError(err));
      }
    };
    run();
  }, [
    session,
    authReady,
    loadAppointments,
    loadLogs,
    loadReminders,
    loadRoles,
    loadInternalUsers,
    loadProviders,
    loadWarehouses,
    loadProviderAppointments,
    isStaff,
    isAdmin,
    isProveedor,
    viewMode,
    filterDay,
    filterMonth,
    filterYear,
  ]);

  useEffect(() => {
    if (!session || !authReady) return undefined;
    if (profileData) return undefined;

    const onConfiguracionesTab =
      (isAdminPanel && adminTab === "configuraciones") ||
      (isLogistica && logisticaTab === "configuraciones") ||
      (isProveedor && proveedorTab === "configuraciones");

    if (onConfiguracionesTab) {
      loadProfile().catch(() => {});
      return undefined;
    }

    const schedule = window.requestIdleCallback
      ? window.requestIdleCallback(() => loadProfile().catch(() => {}), { timeout: 5000 })
      : window.setTimeout(() => loadProfile().catch(() => {}), 2500);

    return () => {
      if (typeof schedule === "number") window.clearTimeout(schedule);
      else if (window.cancelIdleCallback) window.cancelIdleCallback(schedule);
    };
  }, [
    session,
    authReady,
    profileData,
    loadProfile,
    isAdminPanel,
    isLogistica,
    isProveedor,
    adminTab,
    logisticaTab,
    proveedorTab,
  ]);

  useEffect(() => {
    if (!session || !authReady || !selectedWarehouseId) return;
    if (unloadTeamsReadyWarehouseId !== selectedWarehouseId) return;
    const run = async () => {
      try {
        await loadWindows();
        if (isProveedor) {
          const now = new Date();
          const provCal = new Date(now.getFullYear(), now.getMonth() + providerCalendarMonthOffset, 1);
          await loadProviderMonthAvailability(provCal);
          if (providerSelectedDay) await loadProviderDayAvailability(providerSelectedDay);
        }
        if (isAdminPanel && adminTab === "horarios") {
          await loadSpecialDayWindows(specialDay);
          const now = new Date();
          const adminCal = new Date(now.getFullYear(), now.getMonth() + calendarMonthOffset, 1);
          await loadCalendarOverrideSummary(adminCal);
        }
      } catch (err) {
        setError(parseApiError(err));
      }
    };
    run();
  }, [
    session,
    authReady,
    selectedWarehouseId,
    unloadTeamsReadyWarehouseId,
    warehouseSchedulingTeamKey,
    loadWindows,
    isProveedor,
    isAdminPanel,
    adminTab,
    loadProviderMonthAvailability,
    loadProviderDayAvailability,
    loadSpecialDayWindows,
    loadCalendarOverrideSummary,
    providerCalendarMonthOffset,
    calendarMonthOffset,
    providerSelectedDay,
    specialDay,
  ]);

  useEffect(() => {
    const onBuscarCitasTab =
      isStaff && (adminTab === "buscar_citas" || (isLogistica && logisticaTab === "buscar_citas"));
    if (!session || !authReady || !onBuscarCitasTab) return;
    loadReminders().catch(() => {});
  }, [session, authReady, isStaff, adminTab, isLogistica, logisticaTab, loadReminders]);

  useEffect(() => {
    if (!session || !authReady || warehouses.length > 0) return;
    const derived = deriveWarehousesFromAppointments(appointments);
    if (derived.length === 0) return;
    applyWarehouseList(derived);
  }, [session, authReady, warehouses.length, appointments, applyWarehouseList]);

  useEffect(() => {
    if (!session || !authReady) return;
    const refreshData = async () => {
      if (document.visibilityState !== "visible") return;
      try {
        if (isStaff) {
          await loadAppointments();
          const onBuscarCitasTab =
            adminTab === "buscar_citas" || (isLogistica && logisticaTab === "buscar_citas");
          if (onBuscarCitasTab) await loadReminders();
        }
        if (isProveedor) {
          await loadProviderAppointments();
          if (proveedorTab === "inicio" && providerSelectedDay) {
            await loadProviderDayAvailability(providerSelectedDay);
          }
        }
      } catch {
        // Evita ruido visual; los errores de refresco automático no deben bloquear la sesión.
      }
    };
    const intervalId = window.setInterval(refreshData, 45000);
    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        refreshData();
      }
    };
    window.addEventListener("focus", onVisibility);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.clearInterval(intervalId);
      window.removeEventListener("focus", onVisibility);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [
    session,
    authReady,
    isStaff,
    isProveedor,
    proveedorTab,
    providerSelectedDay,
    loadAppointments,
    loadProviderAppointments,
    loadProviderDayAvailability,
    loadReminders,
    adminTab,
    logisticaTab,
    isLogistica,
  ]);

  useEffect(() => {
    if (!isGlobalAdmin || adminTab !== "analitica") return;
    if (analyticsRange === "today" && analyticsDay) {
      setFilterDay(analyticsDay);
      setViewMode("day");
    }
  }, [isGlobalAdmin, adminTab, analyticsRange, analyticsDay]);

  useEffect(() => {
    if (!isAdmin || adminTab !== "analitica") return;
    const run = async () => {
      try {
        await loadAnalytics();
      } catch (err) {
        setError(parseApiError(err));
      }
    };
    run();
  }, [isAdmin, adminTab, loadAnalytics, analyticsRange, analyticsPeriod, analyticsMonth, analyticsYear, analyticsDay, filterWarehouseId]);

  const analyticsPeriodOptions = useMemo(
    () => getAnalyticsPeriodOptions(analyticsRange),
    [analyticsRange]
  );
  const citasReferenceDate = useMemo(() => {
    if (citasRange === "month") return referenceDateForMonthYear(citasMonth, citasYear);
    if (citasRange === "today" && citasDay) {
      const [y, m, d] = String(citasDay).split("-").map(Number);
      if (y && m && d) return new Date(y, m - 1, d, 12, 0, 0);
    }
    return new Date();
  }, [citasRange, citasDay, citasMonth, citasYear]);

  const reviewEffectiveReferenceDate = useMemo(() => {
    if (reviewRange === "month") return referenceDateForMonthYear(reviewMonth, reviewYear);
    if (reviewRange === "today" && reviewDay) {
      const [y, m, d] = String(reviewDay).split("-").map(Number);
      if (y && m && d) return new Date(y, m - 1, d, 12, 0, 0);
    }
    return reviewReferenceDate;
  }, [reviewRange, reviewMonth, reviewYear, reviewDay, reviewReferenceDate]);

  const citasPeriodOptions = useMemo(
    () => getAnalyticsPeriodOptions(citasRange, citasReferenceDate),
    [citasRange, citasReferenceDate]
  );
  const reviewPeriodOptions = useMemo(
    () => getAnalyticsPeriodOptions(reviewRange, reviewEffectiveReferenceDate),
    [reviewRange, reviewEffectiveReferenceDate]
  );
  const viewPeriodOptions = useMemo(
    () => getAnalyticsPeriodOptions(viewMode),
    [viewMode]
  );

  useEffect(() => {
    if (!session || !authReady || !isStaff) return;
    const run = async () => {
      try {
        await loadAppointments();
      } catch (err) {
        const status = err?.response?.status;
        if (status === 401 || status === 403) return;
        setError(parseApiError(err));
      }
    };
    run();
  }, [
    session,
    authReady,
    isStaff,
    loadAppointments,
    viewMode,
    viewPeriod,
    filterDay,
    filterMonth,
    filterYear,
    filterWarehouseId,
    reviewRange,
    reviewPeriod,
    reviewMonth,
    reviewYear,
    reviewDay,
    adminTab,
    logisticaTab,
  ]);

  useEffect(() => {
    if (!isLogistica || logisticaTab !== "citas" || citasRange !== "month") return;
    setFilterMonth(citasMonth);
    setFilterYear(citasYear);
    setViewMode("month");
  }, [isLogistica, logisticaTab, citasRange, citasMonth, citasYear]);

  useEffect(() => {
    const onRevision =
      (isLogistica && logisticaTab === "revision_citas") || (isAdminPanel && adminTab === "revision_citas");
    if (!onRevision || citasRange !== "today" || !citasDay) return;
    setReviewRange("today");
    setReviewDay(citasDay);
  }, [isLogistica, isAdminPanel, logisticaTab, adminTab, citasRange, citasDay]);

  useEffect(() => {
    if (!isAdminPanel || adminTab !== "horarios") return;
    const run = async () => {
      try {
        await loadSpecialDayWindows(specialDay);
      } catch (err) {
        setError(parseApiError(err));
      }
    };
    run();
  }, [isAdmin, adminTab, specialDay, loadSpecialDayWindows]);

  useEffect(() => {
    if (!isAdminPanel || adminTab !== "horarios") return;
    const run = async () => {
      try {
        const now = new Date();
        const targetDate = new Date(now.getFullYear(), now.getMonth() + calendarMonthOffset, 1);
        await loadCalendarOverrideSummary(targetDate);
      } catch (err) {
        setError(parseApiError(err));
      }
    };
    run();
  }, [isAdmin, adminTab, calendarMonthOffset, loadCalendarOverrideSummary, activeAdminFranjaTeamId]);

  useEffect(() => {
    if (!isProveedor || proveedorTab !== "inicio") return;
    const run = async () => {
      try {
        const now = new Date();
        const targetDate = new Date(now.getFullYear(), now.getMonth() + providerCalendarMonthOffset, 1);
        await loadProviderMonthAvailability(targetDate);
      } catch (err) {
        setError(parseApiError(err));
      }
    };
    run();
  }, [
    isProveedor,
    proveedorTab,
    providerCalendarMonthOffset,
    loadProviderMonthAvailability,
    activeProviderUnloadTeamId,
    selectedWarehouseId,
  ]);

  useEffect(() => {
    if (!isProveedor) return;
    if (proveedorTab !== "inicio" && proveedorTab !== "mis_citas" && proveedorTab !== "historial") return;
    const run = async () => {
      try {
        await loadProviderAppointments();
      } catch (err) {
        setError(parseApiError(err));
      }
    };
    run();
  }, [isProveedor, proveedorTab, loadProviderAppointments]);

  useEffect(() => {
    if (!showGlobalAuditPanel && !showWarehouseAuditPanel) return;
    const run = async () => {
      try {
        await loadLogs();
      } catch (err) {
        setError(parseApiError(err));
      }
    };
    run();
  }, [
    showGlobalAuditPanel,
    showWarehouseAuditPanel,
    auditActorId,
    auditAppointmentId,
    auditWarehouseFilter,
    loadLogs,
  ]);

  useEffect(() => {
    if (!isLogistica || logisticaTab !== "historial") return;
    const run = async () => {
      try {
        await loadLogs();
      } catch (err) {
        setError(parseApiError(err));
      }
    };
    run();
  }, [isLogistica, logisticaTab, auditAppointmentId, loadLogs]);

  // Al cambiar filtros/carga del historial, cerramos los paneles de detalle abiertos.
  useEffect(() => {
    setExpandedAuditLogIds([]);
  }, [auditActorId, auditAppointmentId, auditWarehouseFilter, auditTextFilter, auditRoleFilter, logs]);

  const toggleExpandedAuditLog = (logId) => {
    setExpandedAuditLogIds((prev) => {
      const idStr = String(logId);
      const current = prev.map((x) => String(x));
      if (current.includes(idStr)) return prev.filter((x) => String(x) !== idStr);
      return [...prev, logId];
    });
  };

  useEffect(() => {
    if (internalRolesOnly.length > 0 && nuRoleId === "") {
      setNuRoleId(String(internalRolesOnly[0].id));
    }
  }, [internalRolesOnly, nuRoleId]);

  useEffect(() => {
    if (!isAdmin || adminTab !== "proveedores") return;
    const run = async () => {
      try {
        await loadProviders();
      } catch (err) {
        setError(parseApiError(err));
      }
    };
    run();
  }, [isAdmin, adminTab, loadProviders]);

  useEffect(() => {
    if (!isGlobalAdmin || adminTab !== "equipo") return;
    void loadWarehouses();
  }, [isGlobalAdmin, adminTab, loadWarehouses]);

  useEffect(() => {
    // Evita que el navegador/autofill deje valores viejos al entrar al formulario.
    if (isGlobalAdmin && adminTab === "equipo") {
      setNuDoc("");
      setNuEmail("");
      setNuName("");
      setNuPass("");
      setNuPassConfirm("");
      setNuRoleId("");
      setShowNuPass(false);
      setShowNuPassConfirm(false);
    }
  }, [isAdmin, adminTab]);

  const citasInRange = useMemo(() => {
    const period = rangeNeedsPeriodSelector(citasRange) ? citasPeriod : null;
    const { start, end } = getReportRangeBounds(citasRange, citasReferenceDate, period);
    return appointments.filter((a) => {
      if (!matchesWarehouseFilter(a, filterWarehouseId)) return false;
      const dt = new Date(a.start_time);
      return dt >= start && dt < end;
    });
  }, [appointments, citasRange, citasPeriod, citasReferenceDate, filterWarehouseId]);
  const citasRangeCount = useMemo(() => citasInRange.length, [citasInRange]);
  const sinRevisionRangeCount = useMemo(
    () => citasInRange.filter((a) => a.status === "sin_revision").length,
    [citasInRange]
  );
  const revisadasRangeCount = useMemo(
    () => citasInRange.filter((a) => a.status === "revisado").length,
    [citasInRange]
  );
  const finalizadasRangeCount = useMemo(
    () => citasInRange.filter((a) => a.status === "finalizada").length,
    [citasInRange]
  );
  const noPresentadasRangeCount = useMemo(
    () => citasInRange.filter((a) => a.status === "no_presentada").length,
    [citasInRange]
  );
  const canceladasRangeCount = useMemo(
    () => citasInRange.filter((a) => a.status === "cancelado").length,
    [citasInRange]
  );
  const analyticsStatuses = useMemo(
    () => analyticsStatusSummary(analytics?.totales_por_estado || {}),
    [analytics]
  );
  const analyticsStatusesToday = useMemo(
    () => analyticsStatusSummary(analytics?.totales_por_estado_hoy || analytics?.totales_por_estado || {}),
    [analytics]
  );
  const revisadasRangeValue = useMemo(
    () => analyticsStatuses.find((row) => row.key === "revisado")?.value ?? 0,
    [analyticsStatuses]
  );
  const analyticsStatusTotal = useMemo(
    () => analyticsStatuses.reduce((acc, row) => acc + row.value, 0),
    [analyticsStatuses]
  );
  const analyticsTotalCitas = useMemo(() => {
    const fromApi = Number(analytics?.total_citas);
    if (Number.isFinite(fromApi) && fromApi >= 0) return fromApi;
    return analyticsStatusTotal;
  }, [analytics?.total_citas, analyticsStatusTotal]);
  const analyticsMaxStatusValue = useMemo(
    () => Math.max(1, ...analyticsStatusesToday.map((row) => Number(row.value || 0))),
    [analyticsStatusesToday]
  );
  const analyticsTopProviders = useMemo(
    () => (Array.isArray(analytics?.top_proveedores) ? analytics.top_proveedores : []),
    [analytics]
  );
  const analyticsTopProvidersMax = useMemo(
    () => Math.max(1, ...analyticsTopProviders.map((p) => Number(p.cantidad || 0))),
    [analyticsTopProviders]
  );
  const analyticsReferenceDate = useMemo(() => {
    if (analyticsRange === "month") return new Date(Number(analyticsYear), Number(analyticsMonth) - 1, 15);
    if (analyticsRange === "today" && analyticsDay) {
      const [y, m, d] = String(analyticsDay).split("-").map(Number);
      if (y && m && d) return new Date(y, m - 1, d, 12, 0, 0);
    }
    return new Date();
  }, [analyticsRange, analyticsMonth, analyticsYear, analyticsDay]);

  const analyticsRangeLabel = formatReportRangeLabel(
    analyticsRange,
    analyticsReferenceDate,
    rangeNeedsPeriodSelector(analyticsRange) ? analyticsPeriod : null
  );
  const analyticsStatusPie = useMemo(() => {
    if (analyticsStatusTotal <= 0) {
      return "conic-gradient(#e2e8f0 0deg 360deg)";
    }
    let current = 0;
    const slices = analyticsStatuses.map((row) => {
      const angle = (row.value / analyticsStatusTotal) * 360;
      const start = current;
      const end = current + angle;
      current = end;
      return `${row.color} ${start}deg ${end}deg`;
    });
    return `conic-gradient(${slices.join(", ")})`;
  }, [analyticsStatusTotal, analyticsStatuses]);
  const auditRoleOptions = useMemo(() => {
    const roles = new Set(["Admin", "Logistica", "AdminBodega", "Proveedor"]);
    logs.forEach((log) => {
      if (log?.actor_role) roles.add(log.actor_role);
    });
    return Array.from(roles).sort();
  }, [logs]);

  const auditActorOptions = useMemo(() => {
    const byId = new Map();
    logs.forEach((log) => {
      if (!log?.actor_id || byId.has(log.actor_id)) return;
      byId.set(log.actor_id, {
        document_id: log.actor_id,
        full_name: log.actor_name || log.actor_id,
        role_name: log.actor_role || "",
      });
    });
    return Array.from(byId.values()).sort((a, b) =>
      String(a.full_name).localeCompare(String(b.full_name), "es")
    );
  }, [logs]);
  const filteredAuditLogs = useMemo(() => {
    const needle = auditTextFilter.trim().toLowerCase();
    return logs.filter((log) => {
      const haystack = [log.action, log.description, log.actor_name, log.actor_id]
        .map((x) => String(x || "").toLowerCase())
        .join(" ");
      const matchesText = needle.length === 0 || haystack.includes(needle);
      const matchesRole = auditRoleFilter.length === 0 || String(log.actor_role || "") === auditRoleFilter;
      return matchesText && matchesRole;
    });
  }, [logs, auditTextFilter, auditRoleFilter]);
  const filteredLogisticaHistoryLogs = useMemo(() => {
    if (!historyDateFilter) return logs;
    return logs.filter((log) => {
      const d = new Date(log.created_at);
      const y = d.getFullYear();
      const m = String(d.getMonth() + 1).padStart(2, "0");
      const day = String(d.getDate()).padStart(2, "0");
      return `${y}-${m}-${day}` === historyDateFilter;
    });
  }, [logs, historyDateFilter]);
  const reviewAppointments = useMemo(() => {
    const period = rangeNeedsPeriodSelector(reviewRange) ? reviewPeriod : null;
    const { start, end } = getReportRangeBounds(reviewRange, reviewEffectiveReferenceDate, period);
    return appointments.filter((a) => {
      if (!matchesWarehouseFilter(a, filterWarehouseId)) return false;
      if (a.status !== "sin_revision" && a.status !== "revisado") return false;
      const dt = new Date(a.start_time);
      return dt >= start && dt < end;
    });
  }, [appointments, reviewRange, reviewPeriod, filterWarehouseId, reviewEffectiveReferenceDate]);

  const reviewAppointmentsDisplay = useMemo(() => {
    if (!revisionPinnedAppointment) return reviewAppointments;
    const exists = reviewAppointments.some((a) => Number(a.id) === Number(revisionPinnedAppointment.id));
    if (exists) return reviewAppointments;
    return [revisionPinnedAppointment, ...reviewAppointments];
  }, [reviewAppointments, revisionPinnedAppointment]);

  const providerAppointmentsFiltered = useMemo(
    () => providerAppointments.filter((a) => matchesWarehouseFilter(a, providerListWarehouseFilter)),
    [providerAppointments, providerListWarehouseFilter]
  );

  const onCreate = async (payload) => {
    try {
      setError("");
      setSuccess("");
      await api.post(`${API_PREFIX}/crud/appointments`, { ...payload, start_time: new Date(payload.start_time).toISOString() });
      await loadAppointments();
      await loadReminders();
      if (!isAdmin) {
        await loadLogs();
      }
      setSuccess("Cita creada exitosamente.");
    } catch (err) {
      setError(parseApiError(err));
    }
  };

  const onReview = async (id) => {
    await onChangeStatus(id, "revisado");
  };

  const onChangeStatus = async (id, status) => {
    try {
      setError("");
      setSuccess("");
      await api.patch(`${API_PREFIX}/appointments/${id}/status`, { status });
      await loadAppointments();
      await loadReminders();
      await refreshAuditLogsBestEffort();
      setSuccess(`Estado de la cita actualizado a ${providerStatusLabel(status)}.`);
    } catch (err) {
      const message = parseApiError(err);
      setError(message);
      throw new Error(message);
    }
  };

  const onExtend = async (id, extraMinutes = 30) => {
    try {
      setError("");
      setSuccess("");
      const extra = Number(extraMinutes) || 0;
      if (extra <= 0) {
        throw new Error("Minutos extra inválidos.");
      }

      // Validación previa de conflicto (además de la validación en backend).
      const apptRes = await api.get(`${API_PREFIX}/crud/appointments/${id}`);
      const apptPayload = parseApiResponse(apptRes);
      if (!apptPayload.success) {
        throw new Error(apptPayload.message || "No se pudo cargar la cita.");
      }
      const appt = apptPayload.data || {};

      const startTime = appt.start_time;
      const durationNow = Number(appt.duration_minutes) || 0;
      const warehouseId = Number(appt.warehouse_id) || 0;
      const teamId = Number(appt.warehouse_unload_team_id) || 0;
      if (!startTime || durationNow <= 0 || warehouseId <= 0 || teamId <= 0) {
        throw new Error("No se pudo validar el conflicto de la cita (datos incompletos).");
      }

      const conflictRes = await api.get(`${API_PREFIX}/appointments/conflict-check`, {
        params: {
          start_time: startTime,
          duration_minutes: durationNow + extra,
          warehouse_id: warehouseId,
          unload_team_id: teamId,
          exclude_appointment_id: Number(id),
        },
      });
      const conflictPayload = parseApiResponse(conflictRes);
      if (!conflictPayload.success) {
        throw new Error(conflictPayload.message || "No se pudo validar el conflicto.");
      }
      if (conflictPayload.data?.conflict) {
        throw new Error("⚠ Existe un conflicto con otra cita. No se puede extender la duración.");
      }

      const extendRes = await api.patch(`${API_PREFIX}/appointments/${id}/extend`, { extra_minutes: extra });
      const extendPayload = parseApiResponse(extendRes);
      if (!extendPayload.success) {
        throw new Error(extendPayload.message || "No se pudo extender la duración.");
      }
      await loadAppointments();
      await loadReminders();
      await refreshAuditLogsBestEffort();
      if (isLogistica) {
        setSuccess(`Logística añadió +${extra} min. Ver Auditorías para más información.`);
      } else {
        setSuccess(`Se aumentó +${extra} min sobre la reserva original. Ver Auditorías para más información.`);
      }
    } catch (err) {
      const message = parseApiError(err);
      setError(message);
      throw new Error(message);
    }
  };

  const onStaffRescheduleAppointment = async ({
    appointmentId,
    startTime,
    durationMinutes,
    warehouseId,
    warehouseUnloadTeamId,
    confirmNonStandardSlot,
    staffChangeReason,
  }) => {
    try {
      setError("");
      setSuccess("");
      const body = { start_time: startTime };
      if (durationMinutes != null) body.duration_minutes = durationMinutes;
      if (warehouseId != null) body.warehouse_id = warehouseId;
      if (warehouseUnloadTeamId != null) body.warehouse_unload_team_id = warehouseUnloadTeamId;
      if (confirmNonStandardSlot) {
        body.confirm_non_standard_slot = true;
        body.staff_change_reason = staffChangeReason;
      }
      await api.put(`${API_PREFIX}/crud/appointments/${appointmentId}`, body);
      await loadAppointments();
      await loadReminders();
      await refreshAuditLogsBestEffort();
      setSuccess("Cita reprogramada correctamente.");
    } catch (err) {
      const message = parseApiError(err);
      setError(message);
      throw new Error(message);
    }
  };

  const closeProviderNotificationModal = useCallback(() => {
    setProviderNotificationModalOpen(false);
    setProviderNotificationAppointment(null);
    setProviderNotificationModalError("");
    setProviderNotificationRescheduleOpen(false);
  }, []);

  const applyProviderAppointmentContext = useCallback((appt) => {
    if (!appt) return;
    if (appt.warehouse_id) {
      setSelectedWarehouseId(Number(appt.warehouse_id));
    }
    if (appt.warehouse_unload_team_id) {
      setSelectedWarehouseUnloadTeamId(Number(appt.warehouse_unload_team_id));
    }
  }, []);

  const openProviderAppointmentDetail = useCallback(
    async (appointmentId, appointmentHint = null) => {
      if (!appointmentId || !isProveedor) return;
      setError("");
      setProviderNotificationModalOpen(true);
      setProviderNotificationRescheduleOpen(false);
      setProviderNotificationModalError("");
      if (appointmentHint) {
        setProviderNotificationAppointment(appointmentHint);
        setProviderNotificationModalLoading(false);
        applyProviderAppointmentContext(appointmentHint);
        return;
      }
      setProviderNotificationModalLoading(true);
      setProviderNotificationAppointment(null);
      try {
        let appt = providerAppointments.find((a) => Number(a.id) === Number(appointmentId));
        if (!appt) {
          const items = await loadProviderAppointments();
          appt = items.find((a) => Number(a.id) === Number(appointmentId));
        }
        if (!appt) {
          const response = await api.get(`${API_PREFIX}/appointments/${appointmentId}`);
          const payload = parseApiResponse(response);
          if (!payload.success || !payload.data) {
            throw new Error(payload.message || "No se encontró la cita.");
          }
          appt = payload.data;
        }
        setProviderNotificationAppointment(appt);
        applyProviderAppointmentContext(appt);
      } catch (err) {
        setProviderNotificationModalError(parseApiError(err));
        setProviderNotificationAppointment(null);
      } finally {
        setProviderNotificationModalLoading(false);
      }
    },
    [isProveedor, providerAppointments, loadProviderAppointments, applyProviderAppointmentContext]
  );

  const onProviderRescheduleAppointment = async ({ appointmentId, startTime }) => {
    try {
      setError("");
      setSuccess("");
      await api.patch(`${API_PREFIX}/appointments/${appointmentId}/reschedule`, { start_time: startTime });
      await loadProviderAppointments();
      await loadProviderMonthAvailability(providerCalendarBase);
      if (providerSelectedDay) {
        await loadProviderDayAvailability(providerSelectedDay);
      }
      if (
        providerNotificationModalOpen &&
        Number(providerNotificationAppointment?.id) === Number(appointmentId)
      ) {
        closeProviderNotificationModal();
      }
      setSuccess("Cita reprogramada correctamente.");
    } catch (err) {
      const message = parseApiError(err);
      setError(message);
      throw new Error(message);
    }
  };

  const providerStatusLabel = (status) => {
    if (status === "sin_revision") return "Sin revisión";
    if (status === "revisado") return "Revisada";
    if (status === "finalizada") return "Finalizada";
    if (status === "no_presentada") return "No presentada";
    if (status === "cancelado") return "Cancelada";
    return status;
  };

  const onProviderCancelAppointment = async (appointmentId) => {
    try {
      setError("");
      setSuccess("");
      const reason = String(providerCancelReasonById[appointmentId] || "").trim();
      if (reason.length < 5) {
        setError("Debes escribir un motivo de cancelación (mínimo 5 caracteres).");
        return;
      }
      await api.post(`${API_PREFIX}/appointments/${appointmentId}/provider-cancel`, { reason });
      setProviderCancelReasonById((prev) => ({ ...prev, [appointmentId]: "" }));
      await loadProviderAppointments();
      await loadProviderMonthAvailability(providerCalendarBase);
      if (providerSelectedDay) {
        await loadProviderDayAvailability(providerSelectedDay);
      }
      if (
        providerNotificationModalOpen &&
        Number(providerNotificationAppointment?.id) === Number(appointmentId)
      ) {
        closeProviderNotificationModal();
      }
      setSuccess("Cita cancelada exitosamente.");
    } catch (err) {
      setError(parseApiError(err));
    }
  };

  const onCreateUser = async (e) => {
    e.preventDefault();
    try {
      setError("");
      setSuccess("");
      setTeamMessage("");
      if (nuPass !== nuPassConfirm) {
        setError("La contraseña y su confirmación no coinciden.");
        return;
      }
      const strengthError = getPasswordStrengthError(nuPass);
      if (strengthError) {
        setError(strengthError);
        return;
      }
      const warehouseIds = resolveWarehouseIdsForRole(nuRoleName, nuWarehouseIds);
      if (roleNeedsWarehouses(nuRoleName) && warehouseIds.length === 0) {
        setError("Selecciona al menos una bodega para Logística o Administrador de bodega.");
        return;
      }
      await api.post(`${API_PREFIX}/crud/users`, {
        document_id: nuDoc.trim(),
        email: nuEmail.trim(),
        full_name: nuName.trim(),
        password: nuPass,
        role_id: Number(nuRoleId),
        warehouse_ids: warehouseIds,
      });
      setNuDoc("");
      setNuEmail("");
      setNuName("");
      setNuPass("");
      setNuPassConfirm("");
      setNuWarehouseIds([]);
      await loadInternalUsers();
      setTeamMessage("Usuario creado correctamente.");
      setSuccess("Usuario creado exitosamente.");
    } catch (err) {
      setError(parseApiError(err));
    }
  };

  const onStartEditUser = (u) => {
    setError("");
    setTeamMessage("");
    setEditingUserId(u.document_id);
    setEditUserName(u.full_name || "");
    setEditUserEmail(u.email || "");
    const matchedRole = internalRolesOnly.find((r) => r.name === u.role_name);
    setEditUserRoleId(matchedRole ? String(matchedRole.id) : "");
    setEditUserWarehouseIds(
      Array.isArray(u.warehouse_ids) ? u.warehouse_ids.map((id) => String(id)) : []
    );
  };

  const onCancelEditUser = () => {
    setEditingUserId("");
    setEditUserName("");
    setEditUserEmail("");
    setEditUserRoleId("");
    setEditUserWarehouseIds([]);
  };

  const onSaveEditUser = async (documentId) => {
    try {
      setError("");
      setSuccess("");
      setTeamMessage("");
      const saveRoleName =
        internalRolesOnly.find((r) => String(r.id) === String(editUserRoleId))?.name || editRoleName;
      const warehouseIds = resolveWarehouseIdsForRole(saveRoleName, editUserWarehouseIds);
      if (roleNeedsWarehouses(saveRoleName) && warehouseIds.length === 0) {
        setError("Selecciona al menos una bodega para Logística o Administrador de bodega.");
        return;
      }
      await api.put(`${API_PREFIX}/crud/users/${documentId}`, {
        full_name: editUserName.trim(),
        email: editUserEmail.trim(),
        role_id: Number(editUserRoleId),
        warehouse_ids: warehouseIds,
      });
      await loadInternalUsers();
      onCancelEditUser();
      setTeamMessage("Usuario actualizado correctamente.");
      setSuccess("Usuario actualizado exitosamente.");
    } catch (err) {
      setError(parseApiError(err));
    }
  };

  const onDeleteUser = async (documentId) => {
    try {
      setError("");
      setSuccess("");
      setTeamMessage("");
      await api.delete(`${API_PREFIX}/crud/users/${documentId}`);
      await loadInternalUsers();
      if (editingUserId === documentId) {
        onCancelEditUser();
      }
      setTeamMessage("Usuario eliminado correctamente.");
      setSuccess("Usuario eliminado exitosamente.");
    } catch (err) {
      setError(parseApiError(err));
    }
  };

  const onStartEditProvider = (p) => {
    setProvidersMessage("");
    setEditingProviderNit(p.nit);
    setEditProviderCompany(p.company_name || "");
    setEditProviderEmail(p.company_email || "");
    setEditProviderContact(p.contact_name || "");
    setEditProviderContactDoc(p.contact_document || "");
    setEditProviderDigit(p.verification_digit || "");
    setEditProviderPassword("");
  };

  const onCancelEditProvider = () => {
    setEditingProviderNit(null);
    setEditProviderCompany("");
    setEditProviderEmail("");
    setEditProviderContact("");
    setEditProviderContactDoc("");
    setEditProviderDigit("");
    setEditProviderPassword("");
  };

  const onSaveEditProvider = async (nit) => {
    try {
      setError("");
      setSuccess("");
      setProvidersMessage("");
      const body = {
        company_name: editProviderCompany.trim(),
        company_email: editProviderEmail.trim(),
        contact_name: editProviderContact.trim(),
        contact_document: editProviderContactDoc.trim(),
        verification_digit: editProviderDigit.trim(),
      };
      if (editProviderPassword.trim().length >= 6) {
        body.password = editProviderPassword;
      }
      await api.put(`${API_PREFIX}/crud/providers/${nit}`, body);
      await loadProviders();
      onCancelEditProvider();
      setProvidersMessage("Proveedor actualizado. Se envió aviso por correo al proveedor y a los administradores.");
      setSuccess("Proveedor actualizado correctamente.");
    } catch (err) {
      setError(parseApiError(err));
    }
  };

  const onSuspendProvider = async (nit, reason) => {
    try {
      setError("");
      setSuccess("");
      setProvidersMessage("");
      await api.post(`${API_PREFIX}/crud/providers/${nit}/suspend`, { reason: reason.trim() });
      await loadProviders();
      if (editingProviderNit === nit) onCancelEditProvider();
      setProvidersMessage(
        "Proveedor suspendido. No podrá iniciar sesión; en 6 meses se purgarán sus datos (se conserva auditoría)."
      );
      setSuccess("Proveedor suspendido correctamente.");
    } catch (err) {
      setError(parseApiError(err));
    }
  };

  const onReactivateProvider = async (nit) => {
    try {
      setError("");
      setSuccess("");
      setProvidersMessage("");
      await api.post(`${API_PREFIX}/crud/providers/${nit}/reactivate`);
      await loadProviders();
      setProvidersMessage("Proveedor reactivado. Se notificó por correo.");
      setSuccess("Proveedor reactivado correctamente.");
    } catch (err) {
      setError(parseApiError(err));
    }
  };

  const onDeleteProvider = async (nit) => {
    try {
      setError("");
      setSuccess("");
      setProvidersMessage("");
      await api.delete(`${API_PREFIX}/crud/providers/${nit}`);
      await loadProviders();
      if (editingProviderNit === nit) onCancelEditProvider();
      setProvidersMessage("Proveedor eliminado. Solo permanece el registro en auditoría.");
      setSuccess("Proveedor eliminado correctamente.");
    } catch (err) {
      setError(parseApiError(err));
    }
  };

  const formatProviderDate = (iso) => {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleString("es-CO", {
        dateStyle: "short",
        timeStyle: "short",
        hour12: true,
      });
    } catch {
      return "—";
    }
  };

  const formatAuditDateTime = (isoOrDate) => {
    if (!isoOrDate) return "—";
    try {
      const dt = new Date(isoOrDate);
      if (Number.isNaN(dt.getTime())) return String(isoOrDate);
      return dt.toLocaleString("es-CO", {
        dateStyle: "medium",
        timeStyle: "medium",
        hour12: true,
      });
    } catch {
      return "—";
    }
  };

  const formatAuditCriticalValue = (criticalField, raw) => {
    if (raw === null || raw === undefined || raw === "") return "—";
    if (criticalField === "start_time") return formatAuditDateTime(raw);
    if (criticalField === "duration_minutes") return `${raw} min`;
    if (criticalField === "status") return providerStatusLabel(raw);
    return String(raw);
  };

  const onSaveFranjas = async (e) => {
    e.preventDefault();
    try {
      setError("");
      setSuccess("");
      const teamId = activeAdminFranjaTeamId ? Number(activeAdminFranjaTeamId) : null;
      if (!teamId) {
        setError("Selecciona un equipo de descarga de la bodega.");
        return;
      }
      const response = await api.put(`${API_PREFIX}/crud/appointment-franjas`, {
        warehouse_id: selectedWarehouseId,
        unload_team_id: teamId,
        franjas: franjaRows,
      });
      const payload = parseApiResponse(response);
      if (!payload.success) {
        throw new Error(payload.message);
      }
      setWindowsPack(payload.data);
      if (payload.data?.franjas?.length) {
        setFranjaRows(payload.data.franjas.map((w) => ({ start_local: w.start_local, end_local: w.end_local })));
      }
      setSuccess("Franjas semanales guardadas exitosamente.");
    } catch (err) {
      setError(parseApiError(err));
    }
  };

  const onSaveSpecialDayFranjas = async (e) => {
    e?.preventDefault?.();
    try {
      setError("");
      setSuccess("");
      setSpecialDayMessage("");
      if (!specialDayCanEdit) {
        setError("No puedes editar esta fecha: ya pasó o ya tiene citas.");
        return;
      }
      if (specialFranjaValidationError) {
        setError(specialFranjaValidationError);
        return;
      }
      const teamId = activeAdminFranjaTeamId ? Number(activeAdminFranjaTeamId) : null;
      if (!teamId) {
        setError("Selecciona un equipo de descarga de la bodega.");
        return;
      }
      const sortedRows = [...specialFranjaRows].sort((a, b) => String(a.start_local).localeCompare(String(b.start_local)));
      const response = await api.put(`${API_PREFIX}/crud/appointment-franjas/fecha`, {
        day: specialDay,
        warehouse_id: selectedWarehouseId,
        unload_team_id: teamId,
        franjas: sortedRows,
      });
      const payload = parseApiResponse(response);
      if (!payload.success) {
        throw new Error(payload.message);
      }
      const f = payload.data?.franjas || [];
      setSpecialFranjaRows(f.length > 0 ? f.map((w) => ({ start_local: w.start_local, end_local: w.end_local })) : specialFranjaRows);
      setSpecialDayMessage(`Franja especial guardada para ${specialDay}.`);
      await loadCalendarOverrideSummary(calendarBase);
      setSuccess(`Franja especial guardada para ${specialDay}.`);
    } catch (err) {
      setError(parseApiError(err));
    }
  };

  const onSaveBulkDateFranjas = async (e) => {
    e.preventDefault();
    try {
      setError("");
      setSuccess("");
      setBulkMessage("");
      if (bulkEndDay < bulkStartDay) {
        setError("La fecha final debe ser mayor o igual a la inicial.");
        return;
      }
      const sortedRows = [...bulkFranjaRows].sort((a, b) => String(a.start_local).localeCompare(String(b.start_local)));
      for (let i = 0; i < sortedRows.length; i += 1) {
        const row = sortedRows[i];
        if (row.end_local <= row.start_local) {
          setError(`La franja de lote #${i + 1} tiene hora fin menor o igual a la de inicio.`);
          return;
        }
        if (i > 0 && row.start_local < sortedRows[i - 1].end_local) {
          setError(
            `La franja de lote #${i + 1} se solapa con la anterior (puede empezar a las ${formatLocalTime12h(
              sortedRows[i - 1].end_local
            )}, por ejemplo ${formatLocalTime12h("08:00")}–${formatLocalTime12h("09:00")} y ${formatLocalTime12h(
              "09:00"
            )}–${formatLocalTime12h("10:00")}).`
          );
          return;
        }
      }
      const teamId = activeAdminFranjaTeamId ? Number(activeAdminFranjaTeamId) : null;
      if (!teamId) {
        setError("Selecciona un equipo de descarga de la bodega.");
        return;
      }
      const isoWeekdays = [...bulkIsoWeekdays].map(Number).filter((d) => d >= 1 && d <= 7).sort((a, b) => a - b);
      if (isoWeekdays.length === 0) {
        setError("Selecciona al menos un día de la semana para el lote.");
        return;
      }
      const response = await api.put(`${API_PREFIX}/crud/appointment-franjas/fecha/lote`, {
        warehouse_id: selectedWarehouseId,
        unload_team_id: teamId,
        start_day: bulkStartDay,
        end_day: bulkEndDay,
        iso_weekdays: isoWeekdays,
        franjas: sortedRows,
      });
      const payload = parseApiResponse(response);
      if (!payload.success) {
        throw new Error(payload.message);
      }
      const appliedDays = Array.isArray(payload.data?.applied_days) ? payload.data.applied_days : [];
      const skippedDays = Array.isArray(payload.data?.skipped_days) ? payload.data.skipped_days : [];
      const applied = appliedDays.length;
      const skipped = skippedDays.length;
      const skipReasonLabel = (reason) => {
        if (reason === "past_day") return "día pasado";
        if (reason === "has_appointments") return "tiene citas vigentes";
        return reason || "omitido";
      };
      let bulkSummary = `Lote aplicado. Días actualizados: ${applied}. Días omitidos: ${skipped}.`;
      if (skippedDays.length > 0) {
        const details = skippedDays
          .slice(0, 5)
          .map((item) => `${item.day} (${skipReasonLabel(item.reason)})`)
          .join(", ");
        bulkSummary += ` Omitidos: ${details}${skippedDays.length > 5 ? ", ..." : ""}.`;
      }
      setBulkMessage(bulkSummary);
      await loadSpecialDayWindows(specialDay);
      await loadCalendarOverrideSummary(calendarBase);
      if (applied > 0) {
        setSuccess(
          skipped > 0
            ? `Lote aplicado en ${applied} día(s); ${skipped} día(s) se omitieron.`
            : "Lote de franjas aplicado exitosamente."
        );
      } else if (skipped > 0) {
        setError("No se actualizó ningún día del lote. Revisa los días omitidos en el resumen.");
      } else {
        setSuccess("Lote procesado sin cambios.");
      }
    } catch (err) {
      setError(parseApiError(err));
    }
  };

  const onCreateWarehouse = async (e) => {
    e.preventDefault();
    try {
      setError("");
      setSuccess("");
      const name = newWarehouseName.trim();
      if (name.length < 2) {
        setError("El nombre de la bodega debe tener al menos 2 caracteres.");
        return;
      }
      const unloadTeams = Math.min(20, Math.max(1, Number(newWarehouseUnloadTeams) || 1));
      const response = await api.post(`${API_PREFIX}/crud/warehouses`, {
        name,
        address: newWarehouseAddress.trim() || null,
        active: true,
        sort_order: warehouses.length,
        unload_teams: unloadTeams,
      });
      const payload = parseApiResponse(response);
      if (!payload.success) {
        throw new Error(payload.message);
      }
      setNewWarehouseName("");
      setNewWarehouseAddress("");
      setNewWarehouseUnloadTeams(1);
      await loadWarehouses();
      setSuccess("Bodega creada correctamente.");
    } catch (err) {
      setError(parseApiError(err));
    }
  };

  const loadWarehouseTeamNamesForEdit = async (warehouseId) => {
    setWarehouseTeamNamesLoading(true);
    setError("");
    try {
      const response = await api.get(
        `${API_PREFIX}/appointments/unload-teams?warehouse_id=${warehouseId}`
      );
      const payload = parseApiResponse(response);
      const teams = Array.isArray(payload.data) ? payload.data : [];
      const sorted = [...teams].sort(
        (a, b) => Number(a.sort_order ?? 0) - Number(b.sort_order ?? 0) || Number(a.id) - Number(b.id)
      );
      const draft = sorted.map((t, idx) => ({
        id: t.id,
        name: String(t.name || "").trim() || `Equipo ${idx + 1}`,
      }));
      setWarehouseTeamNamesDraft(draft);
      setWarehouseTeamNamesBaseline(draft.map((t) => ({ ...t })));
      setWarehouseTeamNamesEditId(warehouseId);
      setWarehouseRowError((prev) => {
        const next = { ...prev };
        delete next[warehouseId];
        return next;
      });
    } catch (err) {
      setError(parseApiError(err));
      setWarehouseTeamNamesEditId(null);
      setWarehouseTeamNamesDraft([]);
      setWarehouseTeamNamesBaseline([]);
    } finally {
      setWarehouseTeamNamesLoading(false);
    }
  };

  const getWarehouseEquiposCount = useCallback(
    (warehouse) => {
      const draft = warehouseEquiposDraft[warehouse.id];
      if (draft != null) return Math.min(20, Math.max(1, Number(draft) || 1));
      return Math.min(20, Math.max(1, Number(warehouse.unload_teams) || 1));
    },
    [warehouseEquiposDraft]
  );

  const warehouseEquiposCountChanged = useCallback(
    (warehouse) => {
      const draft = warehouseEquiposDraft[warehouse.id];
      if (draft == null) return false;
      return Number(draft) !== Number(warehouse.unload_teams ?? 1);
    },
    [warehouseEquiposDraft]
  );

  const warehouseTeamNamesDirty = useCallback(() => {
    if (!warehouseTeamNamesDraft.length) return false;
    const baselineById = new Map(warehouseTeamNamesBaseline.map((t) => [t.id, t.name]));
    return warehouseTeamNamesDraft.some((t) => t.name !== baselineById.get(t.id));
  }, [warehouseTeamNamesDraft, warehouseTeamNamesBaseline]);

  const hasWarehousePendingChanges = useCallback(
    (warehouse) =>
      warehouseEquiposCountChanged(warehouse) ||
      (warehouseTeamNamesEditId === warehouse.id && warehouseTeamNamesDirty()),
    [warehouseEquiposCountChanged, warehouseTeamNamesEditId, warehouseTeamNamesDirty]
  );

  const persistWarehouseUnloadTeamsCount = async (warehouseId, unloadTeams) => {
    const teams = Math.min(20, Math.max(1, Number(unloadTeams) || 1));
    const response = await api.put(`${API_PREFIX}/crud/warehouses/${warehouseId}`, {
      unload_teams: teams,
    });
    const payload = parseApiResponse(response);
    if (!payload.success) {
      throw new Error(payload.message);
    }
    const updatedRow = payload.data;
    if (updatedRow?.id != null) {
      setWarehouses((prev) =>
        prev.map((row) => (row.id === updatedRow.id ? { ...row, ...updatedRow } : row))
      );
    } else {
      await loadWarehouses();
    }
    if (Number(selectedWarehouseId) === Number(warehouseId)) {
      setAdminFranjaUnloadTeamId("");
      await loadWarehouseUnloadTeams();
    }
    return teams;
  };

  const persistWarehouseTeamNames = async (warehouseId, teamsPayload) => {
    if (!teamsPayload.length) return;
    const response = await api.put(`${API_PREFIX}/crud/warehouses/${warehouseId}/unload-teams`, {
      teams: teamsPayload,
    });
    const payload = parseApiResponse(response);
    if (!payload.success) {
      throw new Error(payload.message);
    }
    if (Number(selectedWarehouseId) === Number(warehouseId)) {
      await loadWarehouseUnloadTeams();
    }
  };

  const onApplyWarehouseChanges = async (warehouse) => {
    const warehouseId = warehouse.id;
    const targetCount = getWarehouseEquiposCount(warehouse);
    const namesPanelOpen = warehouseTeamNamesEditId === warehouseId;
    const localNameDraft =
      namesPanelOpen && warehouseTeamNamesDraft.length
        ? warehouseTeamNamesDraft.slice(0, targetCount)
        : [];

    if (
      !warehouseEquiposCountChanged(warehouse) &&
      !(namesPanelOpen && warehouseTeamNamesDirty())
    ) {
      setError("No hay cambios pendientes. Modifica el número de equipos o los nombres de muelles.");
      return;
    }

    const willSaveCount =
      warehouseEquiposCountChanged(warehouse) || targetCount !== Number(warehouse.unload_teams ?? 1);
    const willSaveNames = namesPanelOpen && warehouseTeamNamesDirty();

    try {
      setWarehouseConfigApplyingId(warehouseId);
      setError("");
      setSuccess("");
      setWarehouseRowError((prev) => {
        const next = { ...prev };
        delete next[warehouseId];
        return next;
      });

      if (willSaveCount) {
        await persistWarehouseUnloadTeamsCount(warehouseId, targetCount);
      }

      let savedNamesPayload = [];
      if (namesPanelOpen && localNameDraft.length) {
        savedNamesPayload = localNameDraft.map((t, idx) => ({
          id: t.id,
          name: (t.name || "").trim() || `Equipo ${idx + 1}`,
        }));
        await persistWarehouseTeamNames(warehouseId, savedNamesPayload);
        await loadWarehouseTeamNamesForEdit(warehouseId);
        if (Number(selectedWarehouseId) === Number(warehouseId)) {
          await loadWarehouseUnloadTeams();
        }
      }

      setWarehouseEquiposDraft((prev) => {
        const next = { ...prev };
        delete next[warehouseId];
        return next;
      });
      const savedNames = namesPanelOpen && savedNamesPayload.length > 0;
      const successMessage =
        savedNames && willSaveCount
          ? "Se guardaron los cambios de la bodega y los muelles."
          : savedNames
            ? "Se guardaron los nombres de los muelles de la bodega."
            : "Se guardó la configuración de equipos de descarga de la bodega.";
      stashWarehouseSaveFlash(successMessage);
      setSuccess(successMessage);
    } catch (err) {
      const msg = parseApiError(err);
      setError(msg);
      setWarehouseRowError((prev) => ({ ...prev, [warehouseId]: msg }));
    } finally {
      setWarehouseConfigApplyingId(null);
    }
  };

  const onDeactivateWarehouse = async (warehouseId) => {
    try {
      setError("");
      setSuccess("");
      const response = await api.delete(`${API_PREFIX}/crud/warehouses/${warehouseId}`);
      const payload = parseApiResponse(response);
      if (!payload.success) {
        throw new Error(payload.message);
      }
      await loadWarehouses();
      setSuccess("Bodega desactivada.");
    } catch (err) {
      setError(parseApiError(err));
    }
  };

  const onClearSpecialDayFranjas = async () => {
    try {
      setError("");
      setSuccess("");
      setSpecialDayMessage("");
      if (!specialDayCanEdit) {
        setError("No puedes editar esta fecha: ya pasó o ya tiene citas.");
        return;
      }
      const clearParams = new URLSearchParams({
        day: specialDay,
        warehouse_id: String(selectedWarehouseId),
      });
      if (activeAdminFranjaTeamId) {
        clearParams.set("unload_team_id", activeAdminFranjaTeamId);
      }
      const response = await api.delete(
        `${API_PREFIX}/crud/appointment-franjas/fecha?${clearParams.toString()}`
      );
      const payload = parseApiResponse(response);
      if (!payload.success) {
        throw new Error(payload.message);
      }
      setSpecialFranjaRows([]);
      setSpecialDayMessage(`Franja especial eliminada para ${specialDay}. Se usará la regla semanal.`);
      await loadCalendarOverrideSummary(calendarBase);
      setSuccess(`Franja especial eliminada para ${specialDay}.`);
    } catch (err) {
      setError(parseApiError(err));
    }
  };

  const onSaveProfile = async (e) => {
    e.preventDefault();
    try {
      setError("");
      setSuccess("");
      const body = {
        full_name: profileFullName.trim(),
        email: profileEmail.trim(),
      };
      const response = await api.put(`${API_PREFIX}/crud/profile/me`, body);
      const payload = parseApiResponse(response);
      if (!payload.success) {
        throw new Error(payload.message);
      }
      setProfileData(payload.data || null);
      setSuccess("Perfil actualizado exitosamente.");
    } catch (err) {
      setError(parseApiError(err));
    }
  };

  const onChangeProfilePassword = async (e) => {
    e.preventDefault();
    try {
      setError("");
      setSuccess("");
      if (profileNewPassword !== profileConfirmPassword) {
        pushToast("La nueva contraseña y su confirmación no coinciden.", "error");
        return;
      }
      const strengthError = getPasswordStrengthError(profileNewPassword);
      if (strengthError) {
        pushToast(strengthError, "error");
        return;
      }
      await api.post(`${API_PREFIX}/crud/profile/me/change-password`, {
        current_password: profileCurrentPassword,
        new_password: profileNewPassword,
      });
      setProfileCurrentPassword("");
      setProfileNewPassword("");
      setProfileConfirmPassword("");
      pushToast("Contraseña actualizada exitosamente.", "success");
    } catch (err) {
      pushToast(parseApiError(err), "error");
    }
  };

  const onUploadProfilePhoto = async (e) => {
    e.preventDefault();
    try {
      setError("");
      setSuccess("");
      setProfilePhotoMessage("");
      // Leer el archivo directamente del input evita casos donde el estado queda en null
      // (por ejemplo, seleccionar el mismo archivo otra vez).
      const fileFromInput = profilePhotoInputRef.current?.files?.[0] || null;
      const fileToUpload = fileFromInput || profilePhotoFile;
      if (!fileToUpload) {
        const msg = "Selecciona una imagen para subir.";
        setError(msg);
        setProfilePhotoMessage(msg);
        return;
      }
      setProfilePhotoFile(fileToUpload);
      const formData = new FormData();
      formData.append("file", fileToUpload);
      const response = await api.post(`${API_PREFIX}/crud/profile/me/photo`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      const payload = parseApiResponse(response);
      if (!payload.success) {
        throw new Error(payload.message);
      }
      setProfileData(payload.data || null);
      setProfilePhotoFile(null);
      setProfilePhotoMessage("Foto actualizada correctamente.");
      if (profilePhotoInputRef.current) {
        profilePhotoInputRef.current.value = "";
      }
      await loadProfile();
      setSuccess("Foto de perfil actualizada exitosamente.");
    } catch (err) {
      const msg = parseApiError(err);
      setError(msg);
      setProfilePhotoMessage(msg);
    }
  };

  const onRemoveProfilePhoto = async () => {
    try {
      setError("");
      setSuccess("");
      setProfilePhotoMessage("");
      const response = await api.delete(`${API_PREFIX}/crud/profile/me/photo`);
      const payload = parseApiResponse(response);
      if (!payload.success) {
        throw new Error(payload.message);
      }
      setProfileData(payload.data || null);
      setProfilePhotoFile(null);
      if (profilePhotoInputRef.current) {
        profilePhotoInputRef.current.value = "";
      }
      setProfilePhotoMessage("Foto eliminada. Se mostrarán tus iniciales.");
      setSuccess("Foto de perfil eliminada exitosamente.");
    } catch (err) {
      const msg = parseApiError(err);
      setError(msg);
      setProfilePhotoMessage(msg);
    }
  };

  const openAnalyticsTab = useCallback(() => {
    if (citasRange === "today" && citasDay) {
      setAnalyticsRange("today");
      setAnalyticsDay(citasDay);
    } else if (citasRange === "month") {
      setAnalyticsRange("month");
      setAnalyticsMonth(citasMonth);
      setAnalyticsYear(citasYear);
    }
    setAdminTab("analitica");
  }, [citasRange, citasDay, citasMonth, citasYear]);

  const goToBuscarCitas = (mode) => {
    if (mode === "day") {
      setViewMode("day");
      setFilterDay(todayISO());
    } else if (mode === "month") {
      const month = citasRange === "month" ? citasMonth : new Date().getMonth() + 1;
      const year = citasRange === "month" ? citasYear : new Date().getFullYear();
      setViewMode("month");
      setFilterMonth(month);
      setFilterYear(year);
    } else {
      setViewMode("list");
    }
    if (isAdmin) {
      setAdminTab("buscar_citas");
    } else if (isLogistica) {
      setLogisticaTab("buscar_citas");
    }
  };

  const openRevisionAppointment = useCallback(
    async (appointmentId, { navigateToRevision = false } = {}) => {
      if (!appointmentId) return;
      if (navigateToRevision) {
        if (isAdminPanel) setAdminTab("revision_citas");
        if (isLogistica) setLogisticaTab("revision_citas");
      }
      setError("");
      setRevisionOpenAppointmentId(Number(appointmentId));
      try {
        const response = await api.get(`${API_PREFIX}/crud/appointments/${appointmentId}`);
        const payload = parseApiResponse(response);
        if (!payload.success || !payload.data) {
          setError(payload.message || "No se encontró la cita.");
          setRevisionOpenAppointmentId(null);
          return;
        }
        const appt = payload.data;
        setRevisionPinnedAppointment(appt);
        const apptDay = calendarDayISOInTimeZone(appt.start_time);
        if (apptDay) setReviewDay(apptDay);
        setReviewReferenceDate(new Date(appt.start_time));
        setReviewRange("today");
        if (appt.warehouse_id) {
          setFilterWarehouseId(String(appt.warehouse_id));
        }
        await loadAppointments();
      } catch (err) {
        setError(parseApiError(err));
        setRevisionOpenAppointmentId(null);
        setRevisionPinnedAppointment(null);
      }
    },
    [loadAppointments, isAdminPanel, isLogistica]
  );

  const handleNotificationNavigate = useCallback(
    (item) => {
      if (!item) return;
      setError("");
      setMobileNavOpen(false);
      if (isProveedor && item.appointment_id) {
        void openProviderAppointmentDetail(item.appointment_id);
        return;
      }
      if (
        item.appointment_id &&
        (isAdminPanel || isLogistica)
      ) {
        void openRevisionAppointment(item.appointment_id, { navigateToRevision: true });
        return;
      }
    },
    [isAdminPanel, isLogistica, isProveedor, openRevisionAppointment, openProviderAppointmentDetail]
  );

  const showCitasSection =
    isStaff && (!isAdminPanel || adminTab === "citas") && (!isLogistica || logisticaTab === "citas");
  const showBuscarCitasSection = isStaff && (adminTab === "buscar_citas" || (isLogistica && logisticaTab === "buscar_citas"));
  const showRevisionSection = isStaff && (adminTab === "revision_citas" || (isLogistica && logisticaTab === "revision_citas"));
  const showLogisticaHistorial = isLogistica && logisticaTab === "historial";
  const showConfiguraciones =
    (isAdminPanel && adminTab === "configuraciones") ||
    (isLogistica && logisticaTab === "configuraciones") ||
    (isProveedor && proveedorTab === "configuraciones");

  const profileDisplayName = profileData?.full_name || session?.email || "Usuario";
  const avatarLetter = getInitials(profileDisplayName);
  const optimizedProfilePhotoUrl = useMemo(() => optimizeCloudinaryImage(profileData?.photo_url, 160), [profileData?.photo_url]);
  const todayValue = todayISO();
  const isSpecialDayPast = specialDay < todayValue;
  const calendarBase = useMemo(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth() + calendarMonthOffset, 1);
  }, [calendarMonthOffset]);
  const workCalendar = useMemo(
    () => buildMonthCalendar(calendarBase, [1, 2, 3, 4, 5, 6, 7]),
    [calendarBase]
  );
  const monthLabel = useMemo(
    () => calendarBase.toLocaleDateString("es-CO", { month: "long", year: "numeric" }),
    [calendarBase]
  );
  const providerCalendarBase = useMemo(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth() + providerCalendarMonthOffset, 1);
  }, [providerCalendarMonthOffset]);
  const providerCalendarLabel = useMemo(
    () => providerCalendarBase.toLocaleDateString("es-CO", { month: "long", year: "numeric" }),
    [providerCalendarBase]
  );
  const providerCalendar = useMemo(
    () => buildMonthCalendar(providerCalendarBase, [1, 2, 3, 4, 5, 6, 7]),
    [providerCalendarBase]
  );
  const providerCanGoPrevMonth = useMemo(() => {
    const now = new Date();
    const cal = providerCalendarBase;
    return (
      cal.getFullYear() > now.getFullYear() ||
      (cal.getFullYear() === now.getFullYear() && cal.getMonth() > now.getMonth())
    );
  }, [providerCalendarBase]);
  const providerDaysWithAppointments = useMemo(() => {
    const set = new Set();
    const tz = String(windowsPack?.timezone || DEFAULT_BUSINESS_TZ);
    providerAppointments.forEach((a) => {
      if (a.status === "cancelado") return;
      if (selectedWarehouseId && Number(a.warehouse_id) !== Number(selectedWarehouseId)) return;
      if (
        activeProviderUnloadTeamId &&
        a.warehouse_unload_team_id != null &&
        Number(a.warehouse_unload_team_id) !== Number(activeProviderUnloadTeamId)
      ) {
        return;
      }
      const iso = calendarDayISOInTimeZone(a.start_time, tz);
      if (iso) set.add(iso);
    });
    return set;
  }, [providerAppointments, windowsPack?.timezone, selectedWarehouseId, activeProviderUnloadTeamId]);
  const providerAvailableSlotKeys = useMemo(
    () => (Array.isArray(providerSelectedSlots) ? providerSelectedSlots : []).map((s) => slotKey(s)),
    [providerSelectedSlots]
  );
  const providerTimeChoiceValid = useMemo(
    () =>
      Boolean(
        providerTimeChoice && providerAvailableSlotKeys.includes(providerTimeChoice)
      ),
    [providerTimeChoice, providerAvailableSlotKeys]
  );
  const providerChosenSlot = useMemo(
    () => (providerTimeChoiceValid ? parseSlotKey(providerTimeChoice) : null),
    [providerTimeChoice, providerTimeChoiceValid]
  );
  const providerNeedsTeamForCalendar = Boolean(
    isProveedor && selectedWarehouseId && warehouseUnloadTeams.length > 0 && !activeProviderUnloadTeamId
  );
  const providerNeedsTeamForSlots = Boolean(
    isProveedor && providerSelectedDay && selectedWarehouseId && !activeProviderUnloadTeamId
  );
  const activeProviderUnloadTeamName = useMemo(() => {
    if (!activeProviderUnloadTeamId) return "";
    const t = warehouseUnloadTeams.find((x) => Number(x.id) === Number(activeProviderUnloadTeamId));
    return t?.name || `Equipo ${activeProviderUnloadTeamId}`;
  }, [activeProviderUnloadTeamId, warehouseUnloadTeams]);

  const providerCannotScheduleSlot = useMemo(() => {
    if (!selectedWarehouseId) return true;
    if (!activeProviderUnloadTeamId) return true;
    if (!providerSelectedDay || providerSelectedDay < todayValue) return true;
    if (providerDayAvailabilityLoading) return true;
    if (providerCreateSubmitting) return true;
    if (providerAvailableSlotKeys.length === 0) return true;
    if (!providerTimeChoice || !providerAvailableSlotKeys.includes(providerTimeChoice)) return true;
    return false;
  }, [
    selectedWarehouseId,
    activeProviderUnloadTeamId,
    providerSelectedDay,
    providerDayAvailabilityLoading,
    providerCreateSubmitting,
    providerAvailableSlotKeys,
    providerTimeChoice,
    todayValue,
  ]);
  const providerSlotAvailabilityCopy = useMemo(
    () =>
      describeProviderSlotAvailability({
        loading: providerDayAvailabilityLoading,
        loadError: providerDayAvailabilityError,
        reason: providerSlotUnavailableReason,
        message: providerSlotUnavailableMessage,
        minimumNoticeHours: providerMinimumNoticeHours,
        selectedDayOpen: providerAvailableDays.includes(providerSelectedDay),
        hasAvailableSlots: providerAvailableSlotKeys.length > 0,
        needsTeamSelection: providerNeedsTeamForSlots || providerNeedsTeamForCalendar,
      }),
    [
      providerDayAvailabilityLoading,
      providerDayAvailabilityError,
      providerSelectedDay,
      providerSlotUnavailableReason,
      providerSlotUnavailableMessage,
      providerMinimumNoticeHours,
      providerAvailableDays,
      providerAvailableSlotKeys,
      providerNeedsTeamForSlots,
      providerNeedsTeamForCalendar,
    ]
  );
  const providerSlotAvailabilityNoticeClass =
    providerSlotAvailabilityCopy.tone === "error"
      ? "border-rose-200 bg-rose-50 text-rose-900"
      : providerSlotAvailabilityCopy.tone === "info"
        ? "border-slate-200 bg-slate-50 text-slate-700"
        : "border-amber-200 bg-amber-50 text-amber-950";

  useEffect(() => {
    if (!isProveedor || proveedorTab !== "inicio") return;
    if (!providerSelectedDay || providerSelectedDay < todayValue) {
      resetProviderSlotSelection();
      return;
    }
    if (!activeProviderUnloadTeamId) {
      resetProviderSlotSelection();
      return;
    }
    void loadProviderDayAvailability(providerSelectedDay);
  }, [
    isProveedor,
    proveedorTab,
    providerSelectedDay,
    activeProviderUnloadTeamId,
    loadProviderDayAvailability,
    todayValue,
    resetProviderSlotSelection,
  ]);

  useEffect(() => {
    if (!isProveedor || proveedorTab !== "inicio") return;
    const today = todayValue;
    const open = (Array.isArray(providerAvailableDays) ? providerAvailableDays : []).filter(
      (d) => String(d) >= today
    );
    if (open.length === 0) return;
    const sel = providerSelectedDay;
    if (!sel || sel < today || !open.includes(sel)) {
      setProviderSelectedDay(open[0]);
    }
  }, [isProveedor, proveedorTab, providerAvailableDays, providerSelectedDay, todayValue]);

  const onProviderCreateAppointment = useCallback(async () => {
    if (providerCreateSubmitting) return;
    try {
      setError("");
      setSuccess("");
      if (!activeProviderUnloadTeamId) {
        setError("Selecciona el muelle / equipo de descarga antes de agendar.");
        return;
      }
      if (!providerSelectedDay) {
        setError("Selecciona un día en el calendario.");
        return;
      }
      if (providerSelectedDay < todayValue) {
        setError("No puedes agendar en un día que ya pasó. Elige hoy o una fecha futura.");
        return;
      }
      const chosen = parseSlotKey(providerTimeChoice);
      if (!chosen || providerAvailableSlotKeys.length === 0 || !providerAvailableSlotKeys.includes(providerTimeChoice)) {
        setError("No hay un turno disponible para agendar en esta fecha.");
        return;
      }
      const desc = providerMaterialDescription.trim();
      if (desc.length < 5) {
        setError("Describe qué vas a entregar (mínimo 5 caracteres).");
        return;
      }
      const [y, m, d] = providerSelectedDay.split("-").map(Number);
      const [hh, mm] = chosen.start_local.split(":").map(Number);
      const localDate = new Date(y, m - 1, d, hh, mm, 0);
      const startTimeIso = localDate.toISOString();
      const createPayload = {
        title: "Entrega de material",
        material_description: desc,
        warehouse_id: selectedWarehouseId,
        warehouse_unload_team_id: activeProviderUnloadTeamId,
        provider_team_index: 1,
        start_time: startTimeIso,
        duration_minutes: chosen.duration_minutes,
      };
      const appointmentIdsBefore = new Set(providerAppointments.map((a) => Number(a.id)));
      setProviderCreateSubmitting(true);
      await warmApi();
      try {
        await api.post(`${API_PREFIX}/appointments`, createPayload, { timeout: API_SLOW_TIMEOUT_MS });
      } catch (postErr) {
        if (!isApiTimeoutError(postErr)) throw postErr;
        const latestAppointments = await loadProviderAppointments();
        const createdDespiteTimeout = latestAppointments.find((a) => {
          if (appointmentIdsBefore.has(Number(a.id))) return false;
          if (Number(a.warehouse_id) !== Number(selectedWarehouseId)) return false;
          if (
            activeProviderUnloadTeamId &&
            a.warehouse_unload_team_id != null &&
            Number(a.warehouse_unload_team_id) !== Number(activeProviderUnloadTeamId)
          ) {
            return false;
          }
          const sameStart = new Date(a.start_time).getTime() === new Date(startTimeIso).getTime();
          const sameDesc = String(a.material_description || "").trim() === desc;
          return sameStart && sameDesc;
        });
        if (createdDespiteTimeout) {
          setProviderMaterialDescription("");
          await loadProviderMonthAvailability(providerCalendarBase);
          await loadProviderDayAvailability(providerSelectedDay);
          setSuccess(
            "Cita agendada correctamente. La respuesta del servidor tardó más de lo habitual; ya aparece en tus citas."
          );
          return;
        }
        throw postErr;
      }
      setProviderMaterialDescription("");
      await loadProviderAppointments();
      await loadProviderMonthAvailability(providerCalendarBase);
      await loadProviderDayAvailability(providerSelectedDay);
      setSuccess("Cita agendada exitosamente.");
    } catch (err) {
      const message = parseApiError(err);
      setError(
        isAppointmentSlotConflict(err)
          ? `${message} Actualizamos los turnos disponibles; elige otro horario si sigue ocupado.`
          : message
      );
      if ((isAppointmentSlotConflict(err) || isApiTimeoutError(err)) && providerSelectedDay) {
        try {
          await loadProviderAppointments();
          await loadProviderDayAvailability(providerSelectedDay);
          await loadProviderMonthAvailability(providerCalendarBase);
        } catch {
          // El toast ya muestra el conflicto; no tapar con error de refresco.
        }
      }
    } finally {
      setProviderCreateSubmitting(false);
    }
  }, [
    providerSelectedDay,
    providerAppointments,
    providerAvailableSlotKeys,
    providerTimeChoice,
    providerMaterialDescription,
    providerCalendarBase,
    selectedWarehouseId,
    activeProviderUnloadTeamId,
    windowsPack?.timezone,
    loadProviderAppointments,
    loadProviderMonthAvailability,
    loadProviderDayAvailability,
    providerCreateSubmitting,
  ]);

  const providerAppointmentsSorted = useMemo(
    () =>
      [...providerAppointmentsFiltered].sort(
        (a, b) => new Date(b.start_time).getTime() - new Date(a.start_time).getTime()
      ),
    [providerAppointmentsFiltered]
  );
  const providerActiveAppointments = useMemo(
    () =>
      providerAppointmentsSorted.filter(
        (a) =>
          a.status !== "cancelado" && a.status !== "finalizada" && a.status !== "no_presentada"
      ),
    [providerAppointmentsSorted]
  );
  const providerHistoryAppointments = useMemo(
    () =>
      providerAppointmentsSorted.filter((a) =>
        a.status === "cancelado" || a.status === "finalizada" || a.status === "no_presentada"
      ),
    [providerAppointmentsSorted]
  );
  const specialFranjaValidationError = useMemo(
    () => getFranjaValidationError(specialFranjaRows, "franja del día"),
    [specialFranjaRows]
  );

  const NavBtn = ({ active, children, onClick, tourId }) => (
    <button
      type="button"
      onClick={() => {
        onClick?.();
        setMobileNavOpen(false);
      }}
      className={`dashboard-nav-btn min-h-11 w-full rounded-lg px-3 py-2.5 text-left text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#35783C]/40 ${
        active
          ? "dashboard-nav-btn--active bg-[#35783C] text-white shadow-md shadow-emerald-900/15"
          : "text-slate-700 hover:bg-emerald-50 hover:text-[#121212]"
      } ${tourId && guidedTourExpectedNavId === tourId ? "tour-menu-highlight" : ""}`}
      aria-current={active ? "page" : undefined}
      data-tour={tourId}
    >
      {children}
    </button>
  );

  const sidebar = (
    <aside
      data-tour="dashboard-sidebar"
      aria-label="Navegación del panel"
      className={`fixed inset-y-0 left-0 z-40 flex w-72 max-w-[85vw] flex-col border-r border-slate-200 bg-white shadow-xl transition-transform lg:static lg:w-64 lg:max-w-none lg:translate-x-0 lg:shadow-sm ${
        mobileNavOpen ? "translate-x-0" : "-translate-x-full"
      } ${panelTourLayout ? "max-lg:!transition-none max-lg:!duration-0" : ""}`}
    >
      <div className="border-b border-slate-100 px-4 py-5" data-tour="sidebar-brand">
        <div>
          <BrandLogo className="h-16 sm:h-20" />
          <p className="text-[11px] text-slate-600">
            Panel{" "}
            {isGlobalAdmin
              ? "administrador"
              : isWarehouseAdmin
                ? "administrador de bodega"
                : isLogistica
                  ? "logística"
                  : "proveedor"}
          </p>
        </div>
      </div>

      <nav className="min-h-0 flex-1 overflow-y-auto px-2 py-3" aria-label="Navegación principal del panel" data-tour="sidebar">
        {isProveedor && (
          <div className="px-2">
            <p
              className="px-2 pb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-600"
              data-tour="nav-section-principal"
            >
              Principal
            </p>
            <NavBtn
              active={proveedorTab === "inicio"}
              tourId="nav-inicio"
              onClick={() => {
                setError("");
                setProveedorTab("inicio");
              }}
            >
              Inicio
            </NavBtn>
            <NavBtn
              active={proveedorTab === "mis_citas"}
              tourId="nav-mis_citas"
              onClick={() => {
                setError("");
                setProveedorTab("mis_citas");
              }}
            >
              Ver mis citas
            </NavBtn>
            <NavBtn
              active={proveedorTab === "historial"}
              tourId="nav-historial"
              onClick={() => {
                setError("");
                setProveedorTab("historial");
              }}
            >
              Historial
            </NavBtn>
            <NavBtn
              active={proveedorTab === "configuraciones"}
              tourId="nav-configuraciones"
              onClick={() => {
                setError("");
                setProveedorTab("configuraciones");
              }}
            >
              Configuraciones
            </NavBtn>
          </div>
        )}

        {isLogistica && (
          <div className="px-2">
            <p
              className="px-2 pb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-600"
              data-tour="nav-section-principal"
            >
              Principal
            </p>
            <NavBtn active={logisticaTab === "citas"} tourId="nav-citas" onClick={() => setLogisticaTab("citas")}>
              Citas
            </NavBtn>
            <NavBtn active={logisticaTab === "buscar_citas"} tourId="nav-buscar_citas" onClick={() => setLogisticaTab("buscar_citas")}>
              Buscar citas
            </NavBtn>
            <NavBtn active={logisticaTab === "revision_citas"} tourId="nav-revision_citas" onClick={() => setLogisticaTab("revision_citas")}>
              Revision de citas
            </NavBtn>
            <NavBtn active={logisticaTab === "historial"} tourId="nav-historial" onClick={() => setLogisticaTab("historial")}>
              Historial
            </NavBtn>
            <NavBtn active={logisticaTab === "configuraciones"} tourId="nav-configuraciones" onClick={() => setLogisticaTab("configuraciones")}>
              Configuraciones
            </NavBtn>
          </div>
        )}

        {isAdminPanel &&
          adminNavEntries.map((entry, idx) =>
            entry.type === "label" ? (
              <p
                key={`l-${idx}`}
                className="px-3 pb-1 pt-3 text-[10px] font-semibold uppercase tracking-wider text-slate-600"
                data-tour={navSectionDataTourFromLabel(entry.text)}
              >
                {entry.text}
              </p>
            ) : (
              <div key={entry.id} className="px-2 pb-0.5">
                <NavBtn active={adminTab === entry.id} tourId={`nav-${entry.id}`} onClick={() => setAdminTab(entry.id)}>
                  {entry.label}
                </NavBtn>
              </div>
            )
          )}
      </nav>

      <div className="border-t border-slate-100 p-3">
        <div
          className="flex items-center gap-3 rounded-lg border border-slate-100 bg-slate-50 px-2 py-2"
          data-tour="sidebar-user-profile"
        >
          {profileData?.photo_url ? (
            <img
              src={optimizedProfilePhotoUrl}
              alt="Foto de perfil"
              crossOrigin="anonymous"
              referrerPolicy="no-referrer"
              loading="lazy"
              decoding="async"
              className="h-9 w-9 shrink-0 rounded-full border border-emerald-100 object-cover"
            />
          ) : (
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-500 text-sm font-bold text-white">
              {avatarLetter}
            </div>
          )}
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-medium text-slate-800">{profileDisplayName}</p>
            <p className="truncate text-[10px] capitalize text-slate-600">{session?.role}</p>
          </div>
        </div>
        <button
          type="button"
          data-tour="sidebar-logout"
          onClick={() => {
            setMobileNavOpen(false);
            logout();
          }}
          className="mt-2 w-full rounded-lg border border-slate-200 py-2 text-xs font-medium text-slate-600 transition hover:bg-slate-50"
        >
          Cerrar sesión
        </button>
      </div>
    </aside>
  );

  const mainHeader = (
    <header className="mb-8" aria-label="Encabezado del módulo activo">
      <p className="text-xs font-medium uppercase tracking-wide text-emerald-600">{activeNavLabel}</p>
      <h1 id="dashboard-page-title" className="mt-1 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
        {saludoHorario()}
      </h1>
      <p className="mt-2 max-w-2xl text-sm text-slate-600">
        {isGlobalAdmin &&
          "Gestiona citas de entrega, franjas horarias, equipo interno, proveedores y auditoría desde un solo panel."}
        {isWarehouseAdmin &&
          "Gestiona citas, bodegas asignadas y franjas horarias de tus bodegas."}
        {isLogistica && "Coordina citas con proveedores y revisa el historial de cambios."}
        {isProveedor && "Consulta información de tu cuenta. Para nuevas citas, contacta a logística o usa los canales acordados."}
      </p>
    </header>
  );

  const citasRangeLabel = formatReportRangeLabel(
    citasRange,
    citasReferenceDate,
    rangeNeedsPeriodSelector(citasRange) ? citasPeriod : null
  );

  const warehouseFilterControl = (selectId, label = "Bodega") => (
    <div>
      <label htmlFor={selectId} className="mb-1 block text-xs font-medium text-slate-600">
        {label}
      </label>
      <select
        id={selectId}
        className={`${input} w-full sm:max-w-xs`}
        value={filterWarehouseId}
        onChange={(e) => setFilterWarehouseId(e.target.value)}
      >
        <option value="">Todas las bodegas</option>
        {warehouses.map((w) => (
          <option key={w.id} value={String(w.id)}>
            {w.name}
          </option>
        ))}
      </select>
    </div>
  );

  const providerWarehouseFilterControl = (
    <div className="mb-3">
      <label htmlFor="provider-list-warehouse" className="mb-1 block text-xs font-medium text-slate-600">
        Filtrar por bodega
      </label>
      <select
        id="provider-list-warehouse"
        className={input + " w-full sm:max-w-xs"}
        value={providerListWarehouseFilter}
        onChange={(e) => setProviderListWarehouseFilter(e.target.value)}
      >
        <option value="">Todas las bodegas</option>
        {warehouses.map((w) => (
          <option key={w.id} value={String(w.id)}>
            {w.name}
          </option>
        ))}
      </select>
    </div>
  );

  const quickActions =
    isAdmin &&
    adminTab === "citas" && (
      <div className="mb-6 space-y-3">
        <div className={`${card} p-4`}>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <label htmlFor="admin-citas-range" className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                Filtro de citas
              </label>
              <select
                id="admin-citas-range"
                name="admin-citas-range"
                className={`${input} w-full`}
                value={citasRange}
                onChange={(e) => {
                  const nextRange = e.target.value;
                  setCitasRange(nextRange);
                  if (rangeNeedsPeriodSelector(nextRange)) {
                    setCitasPeriod(getDefaultPeriodIndex(nextRange));
                  }
                }}
              >
                <option value="today">Día</option>
                <option value="week">Semana</option>
                <option value="biweekly">Quincena</option>
                <option value="month">Mes</option>
              </select>
            </div>
            {citasRange === "today" && (
              <div>
                <label htmlFor="admin-citas-day" className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Día
                </label>
                <input
                  id="admin-citas-day"
                  type="date"
                  className={input}
                  value={citasDay}
                  onChange={(e) => setCitasDay(e.target.value)}
                />
              </div>
            )}
            {rangeNeedsPeriodSelector(citasRange) && (
              <div>
                <label htmlFor="admin-citas-period" className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                  {getPeriodSelectorLabel(citasRange)}
                </label>
                <select
                  id="admin-citas-period"
                  name="admin-citas-period"
                  className={`${input} w-full sm:max-w-xs`}
                  value={citasPeriod ?? 1}
                  onChange={(e) => setCitasPeriod(Number(e.target.value))}
                >
                  {citasPeriodOptions.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
            )}
            {citasRange === "month" && (
              <MonthYearSelects
                month={citasMonth}
                year={citasYear}
                onMonthChange={setCitasMonth}
                onYearChange={setCitasYear}
                inputClass={`${input} w-full`}
                monthId="admin-citas-month"
                yearId="admin-citas-year"
                labelClassName="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500"
              />
            )}
            {warehouseFilterControl("admin-citas-warehouse", "Bodega")}
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          <div className={card}>
            <p className="text-xs font-medium uppercase text-slate-600">Citas agendadas</p>
            <p className="mt-2 text-3xl font-bold text-slate-900">{citasRangeCount}</p>
            <p className="mt-1 text-xs text-slate-600">Rango: {citasRangeLabel}</p>
          </div>
          <div className={card}>
            <p className="text-xs font-medium uppercase text-slate-600">Citas sin revisión</p>
            <p className="mt-2 text-3xl font-bold text-amber-600">{sinRevisionRangeCount}</p>
            <p className="mt-1 text-xs text-slate-600">Pendientes en el rango</p>
          </div>
          <div className={card}>
            <p className="text-xs font-medium uppercase text-slate-600">Citas ya revisadas</p>
            <p className="mt-2 text-3xl font-bold text-emerald-800">{revisadasRangeCount}</p>
            <p className="mt-1 text-xs text-slate-600">Revisadas en el rango</p>
          </div>
          <div className={card}>
            <p className="text-xs font-medium uppercase text-slate-600">Citas finalizadas</p>
            <p className="mt-2 text-3xl font-bold text-blue-600">{finalizadasRangeCount}</p>
            <p className="mt-1 text-xs text-slate-600">Finalizadas en el rango</p>
          </div>
          <div className={card}>
            <p className="text-xs font-medium uppercase text-slate-600">No presentadas</p>
            <p className="mt-2 text-3xl font-bold text-slate-700">{noPresentadasRangeCount}</p>
            <p className="mt-1 text-xs text-slate-600">No presentadas en el rango</p>
          </div>
          <div className={card}>
            <p className="text-xs font-medium uppercase text-slate-600">Canceladas</p>
            <p className="mt-2 text-3xl font-bold text-rose-600">{canceladasRangeCount}</p>
            <p className="mt-1 text-xs text-slate-600">Canceladas en el rango</p>
          </div>
        </div>
      </div>
    );

  const accionesRapidasCitas =
    isAdmin &&
    adminTab === "citas" && (
      <div className={`${card} mb-6`}>
        <p className="mb-3 text-sm font-semibold text-slate-800">Acciones rápidas</p>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className={btnPrimary}
            onClick={() => goToBuscarCitas("day")}
          >
            Ver citas de hoy
          </button>
          <button type="button" className={btnGhost} onClick={() => goToBuscarCitas("list")}>
            Ver todas las citas
          </button>
          <button type="button" className={btnGhost} onClick={() => goToBuscarCitas("month")}>
            Ver citas del mes
          </button>
          <button type="button" className={btnGhost} onClick={openAnalyticsTab}>
            Ver analítica
          </button>
        </div>
      </div>
    );

  return (
    <div className="bg-gradient-to-br from-slate-50 via-white to-emerald-50/50 text-[#121212] max-lg:min-h-0 max-lg:overflow-x-hidden lg:flex lg:min-h-screen lg:h-screen lg:max-h-screen lg:overflow-hidden">
      <ConfirmDialog
        open={Boolean(confirmDeleteUserId)}
        title="Eliminar usuario"
        danger
        confirmLabel="Sí, eliminar"
        onCancel={() => setConfirmDeleteUserId("")}
        onConfirm={() => {
          if (confirmDeleteUserId) onDeleteUser(confirmDeleteUserId);
          setConfirmDeleteUserId("");
        }}
      >
        ¿Seguro que deseas eliminar este usuario? Esta acción no se puede deshacer.
      </ConfirmDialog>
      <ConfirmDialog
        open={confirmDeleteProviderNit != null}
        title="Eliminar proveedor"
        danger
        confirmLabel="Sí, eliminar"
        onCancel={() => setConfirmDeleteProviderNit(null)}
        onConfirm={() => {
          if (confirmDeleteProviderNit != null) onDeleteProvider(confirmDeleteProviderNit);
          setConfirmDeleteProviderNit(null);
        }}
      >
        Solo elimina si no tiene citas. Se borran credenciales y datos; permanece la auditoría del sistema.
      </ConfirmDialog>
      <ConfirmDialog
        open={confirmSuspendProvider != null}
        title="Suspender proveedor"
        danger
        confirmLabel="Suspender"
        onCancel={() => {
          setConfirmSuspendProvider(null);
          setSuspendReason("");
        }}
        onConfirm={() => {
          if (confirmSuspendProvider != null && suspendReason.trim().length >= 3) {
            onSuspendProvider(confirmSuspendProvider, suspendReason);
          } else {
            setError("Indica un motivo de suspensión (mínimo 3 caracteres).");
          }
          setConfirmSuspendProvider(null);
          setSuspendReason("");
        }}
      >
        <p className="mb-3 text-sm text-slate-600">
          El proveedor no podrá iniciar sesión. Tras 6 meses suspendido se eliminarán credenciales, citas y demás datos;
          solo quedará auditoría.
        </p>
        <label htmlFor="suspend-provider-reason" className="mb-1 block text-xs font-medium text-slate-600">Motivo</label>
        <textarea
          id="suspend-provider-reason"
          className={input + " min-h-[80px]"}
          value={suspendReason}
          onChange={(e) => setSuspendReason(e.target.value)}
          placeholder="Ej. Empresa inactiva / registro no válido"
          required
          minLength={3}
        />
      </ConfirmDialog>
      {panelGuidedOpen ? (
        <Suspense fallback={null}>
          <GuidedTourDialog
            open={panelGuidedOpen}
            label="Manual del panel"
            steps={panelGuidedSteps}
            stepIndex={panelGuidedIndex}
            onStepIndexChange={setPanelGuidedIndex}
            onClose={closePanelGuidedTour}
            spotlightLayoutKey={panelTourSpotlightLayoutKey}
          />
        </Suspense>
      ) : null}
      {mobileNavOpen && (
        <button
          type="button"
          className="fixed inset-0 z-30 bg-slate-900/40 lg:hidden"
          onClick={() => setMobileNavOpen(false)}
          aria-label="Cerrar menú lateral"
        />
      )}
      {sidebar}

      <div role="region" aria-label="Preferencias de visualización" className="contents">
        {mobileNavOpen ? <ThemeToggle variant="fixed" className="lg:hidden" /> : null}
        <ThemeToggle variant="fixed" className="hidden lg:inline-flex" />
      </div>

      <main
        id="dashboard-main-content"
        data-tour="main-workspace"
        {...(isProveedor
          ? { "aria-label": "Contenido del panel" }
          : { "aria-labelledby": "dashboard-page-title" })}
        className={`w-full px-4 py-6 pb-[max(12rem,calc(10rem+env(safe-area-inset-bottom,0px)))] sm:px-5 lg:min-h-0 lg:flex-1 lg:overflow-y-auto lg:overscroll-y-contain lg:px-10 lg:py-8 lg:pb-8 ${isProveedor ? "space-y-5" : ""}`}
      >
        <div className="mb-4 rounded-xl border border-slate-200 bg-white px-3 py-2 shadow-sm lg:hidden">
          <div className="flex items-center justify-between gap-3">
            <BrandLogo className="h-7 w-auto shrink-0" protectedArea={false} />
            <div className="flex shrink-0 flex-nowrap items-center gap-1.5">
              <Suspense
                fallback={
                  <button
                    type="button"
                    aria-label="Notificaciones"
                    aria-busy="true"
                    disabled
                    className="relative inline-flex min-h-10 items-center justify-center rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-xs font-semibold uppercase tracking-wide text-slate-700 opacity-70"
                  >
                    <span aria-hidden="true">🔔</span>
                  </button>
                }
              >
                <NotificationCenter compact onNavigate={handleNotificationNavigate} />
              </Suspense>
              <button
                type="button"
                onClick={startManualTour}
                data-tour="manual-btn"
                className="inline-flex min-h-10 items-center rounded-lg border border-slate-300 bg-white px-2 py-2 text-[10px] font-semibold uppercase tracking-wide text-slate-700 transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#35783C]/40 sm:px-3 sm:text-xs"
              >
                Manual
              </button>
              {!mobileNavOpen ? <ThemeToggle variant="inline" /> : null}
              <button
                type="button"
                onClick={() => setMobileNavOpen(true)}
                className="inline-flex min-h-10 items-center justify-center rounded-lg border border-slate-300 px-3 text-sm font-medium text-slate-700 transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#35783C]/40"
                aria-label="Abrir menú lateral"
              >
                Menú
              </button>
            </div>
          </div>
          <p className="mt-1 text-[11px] font-medium uppercase tracking-wide text-slate-600">{activeNavLabel}</p>
        </div>
        <div className="mb-4 hidden flex-nowrap items-center justify-end gap-2 lg:flex">
          <Suspense
            fallback={
              <button
                type="button"
                aria-label="Notificaciones"
                aria-busy="true"
                disabled
                className="relative inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-700 opacity-70"
              >
                <span aria-hidden="true">🔔</span>
                <span className="hidden sm:inline">Notificaciones</span>
              </button>
            }
          >
            <NotificationCenter onNavigate={handleNotificationNavigate} />
          </Suspense>
          <button
            type="button"
            onClick={startManualTour}
            data-tour="manual-btn"
            className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-700 transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#35783C]/40"
          >
            Manual guiado
          </button>
        </div>
        {!isProveedor && mainHeader}
        <ApiStaleBanner />
        {quickActions}
        {accionesRapidasCitas}

        {isProveedor && proveedorTab === "inicio" && (
          <section className="space-y-4" aria-labelledby="proveedor-inicio-title" data-tour="section-proveedor-inicio">
            <header className="rounded-xl border border-emerald-100 bg-white p-5 shadow-sm">
              <p className="text-xs font-medium uppercase tracking-wide text-emerald-800">Proveedor</p>
              <h1 id="proveedor-inicio-title" className="mt-1 text-2xl font-bold tracking-tight text-slate-900">{saludoHorario()}</h1>
              <p className="mt-2 text-sm text-slate-600">
                Elige bodega y muelle (equipo de descarga). El calendario muestra solo los días con franja de{" "}
                <strong>ese equipo</strong>; otra bodega u otro muelle en la misma bodega tienen calendarios distintos.
              </p>
            </header>
            <div className={card}>
              <label htmlFor="provider-warehouse-select" className="mb-1 block text-xs font-medium text-slate-600">Bodega de entrega</label>
              <select
                id="provider-warehouse-select"
                className={input}
                value={selectedWarehouseId ?? ""}
                onChange={(e) => {
                  setSelectedWarehouseId(Number(e.target.value) || null);
                  setProviderSelectedDay(null);
                  setProviderAvailableDays([]);
                  setAdminFranjaUnloadTeamId("");
                  resetProviderSlotSelection();
                }}
              >
                {warehouses.length === 0 && <option value="">Sin bodegas activas</option>}
                {warehouses.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                    {w.unload_teams > 1 ? ` (${w.unload_teams} equipos descarga)` : ""}
                  </option>
                ))}
              </select>
            </div>
            <div className={card}>
              <label htmlFor="provider-unload-team-select" className="mb-1 block text-xs font-medium text-slate-600">
                Muelle / equipo de descarga en la bodega
              </label>
              <select
                id="provider-unload-team-select"
                className={input}
                value={activeProviderUnloadTeamId ?? selectedWarehouseUnloadTeamId ?? ""}
                onChange={(e) => {
                  setSelectedWarehouseUnloadTeamId(Number(e.target.value) || null);
                  setProviderSelectedDay(null);
                  resetProviderSlotSelection();
                }}
                disabled={warehouseUnloadTeams.length === 0}
              >
                {warehouseUnloadTeams.length === 0 && <option value="">Sin equipos en esta bodega</option>}
                {warehouseUnloadTeams.length > 1 && <option value="">Selecciona un muelle…</option>}
                {warehouseUnloadTeams.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-[11px] text-slate-500">
                Cada muelle tiene su propio calendario y turnos en esta bodega.
              </p>
            </div>
            <div className={card}>
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <p className="min-w-0 text-xs font-medium uppercase text-slate-500">
                  Calendario
                  {activeProviderUnloadTeamName ? (
                    <span className="normal-case text-slate-600">
                      {" "}
                      — {activeProviderUnloadTeamName}
                    </span>
                  ) : null}
                </p>
                <div className="flex shrink-0 items-center gap-2">
                  <button
                    type="button"
                    className={btnGhost + " px-2 py-1 text-xs"}
                    disabled={!providerCanGoPrevMonth}
                    onClick={() => providerCanGoPrevMonth && setProviderCalendarMonthOffset((v) => v - 1)}
                    aria-label="Ir al mes anterior del calendario"
                  >
                    ◀
                  </button>
                  <span className="max-w-[9rem] truncate text-center text-xs font-medium capitalize text-slate-700 sm:max-w-none">{providerCalendarLabel}</span>
                  <button type="button" className={btnGhost + " px-2 py-1 text-xs"} onClick={() => setProviderCalendarMonthOffset((v) => v + 1)} aria-label="Ir al mes siguiente del calendario">
                    ▶
                  </button>
                </div>
              </div>
              <div className="mb-1 grid grid-cols-7 gap-1 text-center text-[11px] font-semibold text-slate-500">
                <span>LU</span><span>MA</span><span>MI</span><span>JU</span><span>VI</span><span>SA</span><span>DO</span>
              </div>
              <div className="grid grid-cols-7 gap-1">
                {providerCalendar.cells.map((cell, idx) => {
                  if (!cell) return <div key={`prov-empty-${idx}`} />;
                  const teamReady = Boolean(activeProviderUnloadTeamId);
                  const isPast = cell.isPast || cell.dateISO < todayValue;
                  const hasFranja = !isPast && providerAvailableDays.includes(cell.dateISO);
                  const hasAppointment =
                    hasFranja && providerDaysWithAppointments.has(cell.dateISO);
                  const canPickDay = teamReady && hasFranja;
                  return (
                    <button
                      type="button"
                      key={`prov-${idx}`}
                      disabled={!canPickDay}
                      onClick={() => {
                        if (!canPickDay) return;
                        setProviderSelectedDay(cell.dateISO);
                      }}
                      className={`rounded-md border px-1 py-1.5 text-center text-xs ${
                        !canPickDay
                          ? "cursor-not-allowed border-slate-100 bg-slate-100 text-slate-400"
                          : hasAppointment
                            ? "border-emerald-700 bg-emerald-600 text-white"
                            : "border-emerald-300 bg-emerald-100 text-emerald-900"
                      } ${providerSelectedDay === cell.dateISO && canPickDay ? "ring-2 ring-blue-400/80" : ""}`}
                      title={
                        isPast
                          ? "Este día ya pasó; no puedes agendar aquí"
                          : !teamReady
                            ? "Selecciona un muelle para ver el calendario de ese equipo"
                            : !hasFranja
                              ? "Sin franja para este muelle en esta fecha"
                              : hasAppointment
                                ? "Ya tienes cita este día; puedes agendar otro turno si hay cupo"
                                : "Hay franja publicada: puedes agendar"
                      }
                    >
                      {cell.day}
                    </button>
                  );
                })}
              </div>
              <p className="mt-2 text-[11px] text-slate-600">
                Verde claro: día con franja (puedes agendar). Verde oscuro: ya tienes cita ese día. Gris: sin franja, día pasado o sin
                muelle seleccionado (no se puede hacer clic).
              </p>
            </div>
            <div className={card}>
              <p className="text-xs font-medium uppercase text-slate-500">Día y turno</p>
              <p className="mt-1 text-xs text-slate-600">
                Bodega: <strong>{warehouses.find((w) => Number(w.id) === Number(selectedWarehouseId))?.name || "—"}</strong>
                {" · "}
                Muelle: <strong>{activeProviderUnloadTeamName || "—"}</strong>
                {" · "}
                Día: <strong>{providerSelectedDay ? formatLongEsDateFromISO(providerSelectedDay) : "sin elegir"}</strong>
              </p>
            </div>
            <div className={card}>
              <p className="text-xs font-medium uppercase text-slate-500">Horarios del muelle seleccionado</p>
              {!providerCreateSubmitting &&
                !providerDayAvailabilityLoading &&
                providerCannotScheduleSlot &&
                providerSlotAvailabilityCopy.title && (
                <div
                  className={`mt-3 rounded-lg border px-3 py-2 text-sm ${providerSlotAvailabilityNoticeClass}`}
                  role="alert"
                >
                  <p className="font-medium">{providerSlotAvailabilityCopy.title}</p>
                  {providerSlotAvailabilityCopy.detail && (
                    <p className="mt-1 text-xs leading-relaxed">{providerSlotAvailabilityCopy.detail}</p>
                  )}
                </div>
              )}
              <div className="mt-3 grid gap-2 md:grid-cols-2">
                <div className="md:col-span-2">
                  <label htmlFor="provider-slot-select" className="mb-1 block text-xs font-medium text-slate-600">Turno disponible</label>
                  <select
                    id="provider-slot-select"
                    className={input}
                    value={providerTimeChoiceValid ? providerTimeChoice : ""}
                    onChange={(e) => setProviderTimeChoice(e.target.value)}
                    disabled={providerCannotScheduleSlot}
                  >
                    {providerAvailableSlotKeys.length === 0 ? (
                      <option value="">{providerSlotAvailabilityCopy.optionLabel}</option>
                    ) : (
                      providerSelectedSlots.map((slot) => (
                        <option key={slotKey(slot)} value={slotKey(slot)}>
                          {formatSlotLabel(slot)}
                        </option>
                      ))
                    )}
                  </select>
                </div>
                {providerChosenSlot && (
                  <div className="md:col-span-2">
                    <p className="text-xs text-slate-600">
                      Duración del turno seleccionado: <strong>{providerChosenSlot.duration_minutes} minutos</strong>
                    </p>
                  </div>
                )}
              </div>
              <div className="mt-2">
                <label htmlFor="provider-material-description" className="mb-1 block text-xs font-medium text-slate-600">
                  Descripción de lo que vas a entregar
                </label>
                <textarea
                  id="provider-material-description"
                  className={input + " min-h-[88px]"}
                  value={providerMaterialDescription}
                  onChange={(e) => setProviderMaterialDescription(e.target.value)}
                  placeholder="Ej.: Tornillería, perfiles metálicos, etc."
                />
              </div>
              <button
                type="button"
                className={btnPrimary + " mt-3"}
                onClick={() => {
                  if (providerCannotScheduleSlot) return;
                  void onProviderCreateAppointment();
                }}
                disabled={providerCannotScheduleSlot}
                aria-busy={providerCreateSubmitting}
              >
                {providerCreateSubmitting ? "Guardando cita…" : "Agendar cita"}
              </button>
            </div>
          </section>
        )}

        {isProveedor && proveedorTab === "mis_citas" && (
          <div className="space-y-4">
            <header className="rounded-xl border border-emerald-100 bg-white p-5 shadow-sm">
              <p className="text-xs font-medium uppercase tracking-wide text-emerald-600">Proveedor</p>
              <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">Mis citas</h1>
              <p className="mt-2 text-sm text-slate-600">
                Consulta tus citas y usa <strong>Ver más info</strong> para ver el detalle, reprogramar o cancelar.
              </p>
            </header>
            <div className={card}>
              <p className="text-xs font-medium uppercase text-slate-500">Mis citas</p>
              {providerWarehouseFilterControl}
              <div className="mt-2 space-y-3">
                {providerActiveAppointments.length === 0 && (
                  <p className="text-sm text-slate-500">Aún no tienes citas agendadas.</p>
                )}
                {providerActiveAppointments.map((a) => {
                  const descPreview = String(a.material_description || "").trim();
                  const shortDesc =
                    descPreview.length > 72 ? `${descPreview.slice(0, 72)}…` : descPreview;
                  return (
                    <div
                      key={a.id}
                      className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold text-slate-900">Cita #{a.id}</p>
                        <p className="mt-0.5 text-sm text-slate-700">
                          {new Date(a.start_time).toLocaleString("es-CO", {
                            dateStyle: "medium",
                            timeStyle: "short",
                            hour12: true,
                          })}
                        </p>
                        {a.warehouse_name && (
                          <p className="mt-1 text-xs text-slate-600">Bodega: {a.warehouse_name}</p>
                        )}
                        {a.warehouse_unload_team_name && (
                          <p className="text-xs text-slate-600">Muelle: {a.warehouse_unload_team_name}</p>
                        )}
                        <p className="mt-1 text-xs text-slate-600">Estado: {providerStatusLabel(a.status)}</p>
                        {shortDesc && (
                          <p className="mt-1 text-xs text-slate-500 line-clamp-2">Descripción: {shortDesc}</p>
                        )}
                      </div>
                      <button
                        type="button"
                        className="shrink-0 rounded-lg border border-[#35783C] bg-emerald-50 px-4 py-2 text-sm font-semibold text-[#35783C] hover:bg-emerald-100"
                        onClick={() => void openProviderAppointmentDetail(a.id, a)}
                      >
                        Ver más info
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {isProveedor && proveedorTab === "historial" && (
          <div className="space-y-4">
            <header className="rounded-xl border border-emerald-100 bg-white p-5 shadow-sm">
              <p className="text-xs font-medium uppercase tracking-wide text-emerald-600">Proveedor</p>
              <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">Historial</h1>
              <p className="mt-2 text-sm text-slate-600">Aquí ves citas canceladas, finalizadas o no presentadas.</p>
            </header>
            <div className={card}>
              <p className="text-xs font-medium uppercase text-slate-500">Historial de citas</p>
              {providerWarehouseFilterControl}
              <div className="mt-2 space-y-2">
                {providerHistoryAppointments.length === 0 && <p className="text-sm text-slate-500">No tienes historial todavía.</p>}
                {providerHistoryAppointments.map((a) => (
                  <div
                    key={a.id}
                    className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-slate-900">Cita #{a.id}</p>
                      <p className="mt-0.5 text-sm text-slate-700">
                        {new Date(a.start_time).toLocaleString("es-CO", {
                          dateStyle: "medium",
                          timeStyle: "short",
                          hour12: true,
                        })}
                      </p>
                      {a.warehouse_name && (
                        <p className="mt-1 text-xs text-slate-600">Bodega: {a.warehouse_name}</p>
                      )}
                      <p className="mt-1 text-xs text-slate-600">Estado: {providerStatusLabel(a.status)}</p>
                    </div>
                    <button
                      type="button"
                      className="shrink-0 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                      onClick={() => void openProviderAppointmentDetail(a.id, a)}
                    >
                      Ver más info
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {isGlobalAdmin && adminTab === "analitica" && (
          <div className={card}>
            <h2 className="mb-4 text-lg font-semibold text-slate-900">Analítica</h2>
            <div className="mb-4 rounded-lg border border-slate-200 bg-slate-50/50 p-4">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div>
                  <label htmlFor="analytics-range-filter" className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Filtro de analítica
                  </label>
                  <select
                    id="analytics-range-filter"
                    name="analytics-range-filter"
                    className={`${input} w-full`}
                    value={analyticsRange}
                    onChange={(e) => {
                      const nextRange = e.target.value;
                      setAnalyticsRange(nextRange);
                      if (rangeNeedsPeriodSelector(nextRange)) {
                        setAnalyticsPeriod(getDefaultPeriodIndex(nextRange));
                      }
                    }}
                  >
                    <option value="today">Día</option>
                    <option value="week">Semana</option>
                    <option value="biweekly">Quincena</option>
                    <option value="month">Mes</option>
                  </select>
                </div>
                {analyticsRange === "today" && (
                  <div>
                    <label htmlFor="analytics-day-filter" className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Día
                    </label>
                    <input
                      id="analytics-day-filter"
                      type="date"
                      className={input}
                      value={analyticsDay}
                      onChange={(e) => setAnalyticsDay(e.target.value)}
                    />
                  </div>
                )}
                {analyticsRange === "month" && (
                  <>
                    <div>
                      <label htmlFor="analytics-month-filter" className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Mes
                      </label>
                      <select
                        id="analytics-month-filter"
                        name="analytics-month-filter"
                        className={`${input} w-full`}
                        value={analyticsMonth}
                        onChange={(e) => setAnalyticsMonth(Number(e.target.value))}
                      >
                        <option value={1}>Enero</option>
                        <option value={2}>Febrero</option>
                        <option value={3}>Marzo</option>
                        <option value={4}>Abril</option>
                        <option value={5}>Mayo</option>
                        <option value={6}>Junio</option>
                        <option value={7}>Julio</option>
                        <option value={8}>Agosto</option>
                        <option value={9}>Septiembre</option>
                        <option value={10}>Octubre</option>
                        <option value={11}>Noviembre</option>
                        <option value={12}>Diciembre</option>
                      </select>
                    </div>
                    <div>
                      <label htmlFor="analytics-year-filter" className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Año
                      </label>
                      <select
                        id="analytics-year-filter"
                        name="analytics-year-filter"
                        className={`${input} w-full`}
                        value={analyticsYear}
                        onChange={(e) => setAnalyticsYear(Number(e.target.value))}
                      >
                        {Array.from({ length: 7 }).map((_, i) => {
                          const y = new Date().getFullYear() - 3 + i;
                          return (
                            <option key={`analytics-year-${y}`} value={y}>
                              {y}
                            </option>
                          );
                        })}
                      </select>
                    </div>
                  </>
                )}
                {rangeNeedsPeriodSelector(analyticsRange) && (
                  <div>
                    <label htmlFor="analytics-period-filter" className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                      {getPeriodSelectorLabel(analyticsRange)}
                    </label>
                    <select
                      id="analytics-period-filter"
                      name="analytics-period-filter"
                      className={`${input} w-full`}
                      value={analyticsPeriod ?? 1}
                      onChange={(e) => setAnalyticsPeriod(Number(e.target.value))}
                    >
                      {analyticsPeriodOptions.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
                {warehouseFilterControl("analytics-warehouse", "Bodega")}
              </div>
            </div>
            {(analyticsLoading || !analytics) && (
              <p className="text-sm text-slate-500">Cargando analítica…</p>
            )}
            {analytics && !analyticsLoading && analyticsTotalCitas === 0 ? (
              <p className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                Sin citas para {analyticsRangeLabel}.
              </p>
            ) : null}
            {analytics && !analyticsLoading && (
              <div className="grid gap-4 md:grid-cols-3">
                <div className={inlay + " md:col-span-1"}>
                  <p className="text-xs font-medium uppercase text-slate-500">Citas en el rango ({analyticsRangeLabel})</p>
                  <p className="mt-2 text-2xl font-bold text-slate-900">{analyticsTotalCitas}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    Revisadas: <span className="font-semibold text-emerald-600">{revisadasRangeValue}</span>
                  </p>
                </div>
                <div className={inlay + " md:col-span-2"}>
                  <p className="text-xs font-medium uppercase text-slate-500">Por estado ({analyticsRangeLabel})</p>
                  <div className="mt-3 flex flex-wrap items-center gap-6">
                    <div className="relative h-40 w-40 rounded-full border border-slate-200 sm:h-52 sm:w-52" style={{ background: analyticsStatusPie }}>
                      <div className="absolute left-1/2 top-1/2 h-16 w-16 -translate-x-1/2 -translate-y-1/2 rounded-full border border-slate-100 bg-white sm:h-20 sm:w-20" />
                    </div>
                    <ul className="space-y-1 text-sm text-slate-700">
                      {analyticsStatuses.map((row) => (
                        <li key={row.key} className="flex items-center gap-2">
                          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: row.color }} />
                          <span className="font-medium" style={{ color: row.color }}>
                            {row.label}
                          </span>
                          <span className="text-slate-700">: {row.value}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
                <div className={`${inlay} md:col-span-2`}>
                  <p className="text-xs font-medium uppercase text-slate-500">
                    {analyticsRange === "today"
                      ? `Citas del día (${analyticsRangeLabel})`
                      : "Citas por día de la semana"}
                  </p>
                  <ul className="mt-2 grid gap-1 sm:grid-cols-2 text-sm text-slate-700">
                    {(analytics.citas_por_dia_semana || []).map((row) => (
                      <li key={row.fecha} className="flex justify-between rounded-lg border border-slate-100 bg-white px-2 py-1.5">
                        <span>
                          {row.dia} <span className="text-slate-500">({row.fecha})</span>
                        </span>
                        <span className="font-medium text-emerald-600">{row.cantidad}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div className={`${inlay} md:col-span-2`}>
                  <p className="text-xs font-medium uppercase text-slate-500">
                    Diagrama de barras por estado ({analyticsRangeLabel})
                  </p>
                  <div className="mt-3 space-y-2">
                    {analyticsStatusesToday.map((row) => {
                      const widthPct = Math.round((Number(row.value || 0) / analyticsMaxStatusValue) * 100);
                      return (
                        <div key={`bar-${row.key}`} className="grid grid-cols-[minmax(88px,120px)_1fr_32px] items-center gap-2 text-xs sm:text-sm">
                          <span className="text-slate-700">{row.label}</span>
                          <div className="h-4 rounded bg-slate-100">
                            <div
                              className="h-4 rounded"
                              style={{ width: `${widthPct}%`, backgroundColor: row.color, minWidth: row.value > 0 ? "8px" : "0px" }}
                            />
                          </div>
                          <span className="text-right font-medium text-slate-700">{row.value}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
                <div className={`${inlay} md:col-span-3`}>
                  <p className="text-xs font-medium uppercase text-slate-500">Top 10 proveedores por citas del mes (barras verticales)</p>
                  {analyticsTopProviders.length === 0 ? (
                    <p className="mt-2 text-sm text-slate-500">Sin datos.</p>
                  ) : (
                    <div className="mt-3 flex items-end gap-3 overflow-x-auto pb-1">
                      {analyticsTopProviders.map((p) => {
                        const heightPct = Math.round((Number(p.cantidad || 0) / analyticsTopProvidersMax) * 100);
                        return (
                          <div key={`provider-bar-${p.nit}`} className="flex min-w-[92px] flex-col items-center gap-2">
                            <div className="text-xs font-semibold text-emerald-700">{p.cantidad}</div>
                            <div className="flex h-40 w-12 items-end rounded bg-slate-100 p-1">
                              <div
                                className="w-full rounded bg-emerald-500"
                                style={{ height: `${heightPct}%`, minHeight: p.cantidad > 0 ? "8px" : "0px" }}
                              />
                            </div>
                            <div className="text-center text-[11px] text-slate-600">
                              <div className="truncate font-medium">{p.nombre || `NIT ${p.nit}`}</div>
                              <div className="text-slate-500">NIT {p.nit}</div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {isAdminPanel && adminTab === "bodegas" && (
          <div className={card}>
            <h2 className="mb-2 text-lg font-semibold text-slate-900">Bodegas de entrega</h2>
            <p className="mb-4 text-xs text-slate-600">
              Cada bodega tiene su calendario de turnos y <strong>equipos de descarga</strong> (citas simultáneas en el mismo horario).
              Cambia <em>Equipos</em> o abre <strong>Nombres de muelles</strong> y pulsa <strong>Aplicar cambios</strong> en esa fila.
            </p>
            {isGlobalAdmin && (
              <form className="mb-6 grid gap-2 md:grid-cols-3" onSubmit={onCreateWarehouse}>
                <input
                  className={input}
                  placeholder="Nombre de la bodega"
                  value={newWarehouseName}
                  onChange={(e) => setNewWarehouseName(e.target.value)}
                  required
                />
                <input
                  className={input}
                  placeholder="Dirección (opcional)"
                  value={newWarehouseAddress}
                  onChange={(e) => setNewWarehouseAddress(e.target.value)}
                />
                <label className="flex flex-col gap-1 text-xs text-slate-600">
                  Equipos de descarga
                  <input
                    className={input}
                    type="number"
                    min={1}
                    max={20}
                    value={newWarehouseUnloadTeams}
                    onChange={(e) => setNewWarehouseUnloadTeams(e.target.value)}
                  />
                </label>
                <button type="submit" className={btnPrimary + " md:col-span-3"}>
                  Agregar bodega
                </button>
              </form>
            )}
            {isWarehouseAdmin && (
              <p className="mb-4 text-xs text-amber-800">
                Solo puedes configurar las bodegas que te asignó el administrador global.
              </p>
            )}
            <ul className="space-y-2">
              {warehouses.map((w) => (
                <li
                  key={w.id}
                  className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="font-medium text-slate-800">{w.name}</p>
                      {w.address && <p className="text-xs text-slate-500">{w.address}</p>}
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <label className="flex items-center gap-1 text-xs text-slate-600">
                        Equipos
                        <input
                          className={input + " w-16 py-1 text-center"}
                          type="number"
                          min={1}
                          max={20}
                          value={getWarehouseEquiposCount(w)}
                          onChange={(e) => {
                            const n = Math.min(20, Math.max(1, Number(e.target.value) || 1));
                            setWarehouseEquiposDraft((prev) => ({ ...prev, [w.id]: n }));
                            if (warehouseTeamNamesEditId === w.id) {
                              setWarehouseTeamNamesDraft((prev) => prev.slice(0, n));
                            }
                          }}
                        />
                      </label>
                      <button
                        type="button"
                        className={btnPrimary + " px-3 py-1 text-xs"}
                        disabled={
                          warehouseConfigApplyingId === w.id || !hasWarehousePendingChanges(w)
                        }
                        title={
                          hasWarehousePendingChanges(w)
                            ? "Guardar cantidad de muelles y/o nombres"
                            : "Primero cambia Equipos o edita nombres de muelles"
                        }
                        onClick={() => void onApplyWarehouseChanges(w)}
                      >
                        {warehouseConfigApplyingId === w.id ? "Aplicando…" : "Aplicar cambios"}
                      </button>
                      {(w.unload_teams ?? 1) >= 1 && (
                        <button
                          type="button"
                          className="text-xs font-medium text-sky-700 underline hover:text-sky-900"
                          onClick={() => {
                            if (warehouseTeamNamesEditId === w.id) {
                              setWarehouseTeamNamesEditId(null);
                              setWarehouseTeamNamesDraft([]);
                              setWarehouseTeamNamesBaseline([]);
                            } else {
                              void loadWarehouseTeamNamesForEdit(w.id);
                            }
                          }}
                        >
                          {warehouseTeamNamesEditId === w.id ? "Ocultar nombres" : "Nombres de muelles"}
                        </button>
                      )}
                      {isGlobalAdmin && (
                        <button
                          type="button"
                          className="text-xs text-rose-700 underline hover:text-rose-800 disabled:opacity-40"
                          disabled={warehouses.filter((x) => x.active).length <= 1}
                          onClick={() => void onDeactivateWarehouse(w.id)}
                        >
                          Desactivar
                        </button>
                      )}
                    </div>
                  </div>
                  {warehouseRowError[w.id] && (
                    <p className="mt-2 rounded-lg border border-rose-200 bg-rose-50 px-2 py-1.5 text-xs text-rose-800" role="alert">
                      {warehouseRowError[w.id]}
                    </p>
                  )}
                  {warehouseTeamNamesEditId === w.id && (
                    <div className="mt-3 border-t border-slate-200 pt-3">
                      <p className="mb-2 text-xs text-slate-600">
                        Asigna un nombre a cada muelle (ej. Carlos, Rubén) y pulsa <strong>Aplicar cambios</strong> en
                        esa fila; verás un mensaje de confirmación. Para <strong>quitar muelles</strong>,
                        baja <em>Equipos</em> y aplica (no si ese muelle tiene citas activas).
                      </p>
                      {warehouseTeamNamesLoading && (
                        <p className="text-xs text-slate-500">Cargando equipos…</p>
                      )}
                      {!warehouseTeamNamesLoading && warehouseTeamNamesDraft.length === 0 && (
                        <p className="text-xs text-slate-500">Sin equipos en esta bodega.</p>
                      )}
                      <ul className="space-y-2">
                        {warehouseTeamNamesDraft
                          .slice(0, getWarehouseEquiposCount(w))
                          .map((t, idx) => (
                          <li key={t.id} className="flex flex-wrap items-center gap-2">
                            <label
                              htmlFor={`team-name-${w.id}-${t.id}`}
                              className="w-24 shrink-0 text-xs text-slate-500"
                            >
                              Muelle {idx + 1}
                            </label>
                            <input
                              id={`team-name-${w.id}-${t.id}`}
                              className={input + " min-w-[10rem] flex-1"}
                              type="text"
                              maxLength={80}
                              value={t.name}
                              placeholder={`Ej. ${idx === 0 ? "Carlos" : idx === 1 ? "Rubén" : "Nombre"}`}
                              onChange={(e) => {
                                const value = e.target.value;
                                setWarehouseTeamNamesDraft((prev) =>
                                  prev.map((row) => (row.id === t.id ? { ...row, name: value } : row))
                                );
                              }}
                            />
                          </li>
                        ))}
                      </ul>
                      {warehouseTeamNamesDraft.length > 0 && (
                        <div className="sticky bottom-0 mt-3 flex flex-wrap items-center gap-2 border-t border-slate-200 bg-slate-50 py-3">
                          <button
                            type="button"
                            className={btnPrimary}
                            disabled={
                              warehouseConfigApplyingId === w.id || !hasWarehousePendingChanges(w)
                            }
                            onClick={() => void onApplyWarehouseChanges(w)}
                          >
                            {warehouseConfigApplyingId === w.id ? "Aplicando…" : "Aplicar cambios"}
                          </button>
                          {!hasWarehousePendingChanges(w) && (
                            <span className="text-xs text-slate-500">Edita equipos o nombres para habilitar.</span>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {isAdminPanel && adminTab === "horarios" && (
          <div className={card}>
            <h2 className="mb-2 text-lg font-semibold text-slate-900">Turnos por bodega y fecha</h2>
            <p className="mb-4 text-xs text-slate-600">
              Define turnos explícitos por bodega (ej. 1:00 PM–2:00 PM de 60 min, 2:00 PM–2:30 PM de 30 min). Zona horaria:{" "}
              {windowsPack?.timezone || "America/Bogota"}.
            </p>
            <div className="mb-4">
              <label htmlFor="admin-franja-warehouse-select" className="mb-1 block text-xs font-medium text-slate-600">
                Bodega a configurar
              </label>
              <select
                id="admin-franja-warehouse-select"
                className={input}
                value={selectedWarehouseId ?? ""}
                onChange={(e) => {
                  setSelectedWarehouseId(Number(e.target.value) || null);
                  setAdminFranjaUnloadTeamId("");
                  setTeamHasWeeklyFranjas(false);
                  setCalendarOverrideDays([]);
                  setSpecialFranjaRows([]);
                  setFranjaRows([]);
                }}
              >
                {warehouses.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="mb-4">
              <label htmlFor="admin-franja-team-select" className="mb-1 block text-xs font-medium text-slate-600">
                Equipo de descarga (horarios de este muelle)
              </label>
              <select
                id="admin-franja-team-select"
                className={input}
                value={activeAdminFranjaTeamId || adminFranjaUnloadTeamId}
                onChange={(e) => setAdminFranjaUnloadTeamId(e.target.value)}
                disabled={warehouseUnloadTeams.length === 0}
              >
                {warehouseUnloadTeams.length === 0 && (
                  <option value="">Sin equipos — configúralos en Bodegas</option>
                )}
                {warehouseUnloadTeams.map((t) => (
                  <option key={`franja-team-${t.id}`} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-[11px] text-slate-500">
                Cada bodega tiene sus propios equipos (
                {warehouses.find((w) => Number(w.id) === Number(selectedWarehouseId))?.unload_teams ?? 1}{" "}
                en esta bodega). Cambia de equipo para definir horarios distintos; otra bodega es independiente.
              </p>
            </div>
            <form className="space-y-3" onSubmit={onSaveFranjas}>
              <div>
                <p className="mt-2 text-xs text-slate-500">Hoy es {formatLongEsDate(new Date())}.</p>
                <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <p className="min-w-0 text-sm font-medium text-slate-700">Calendario de días habilitados</p>
                    <div className="flex shrink-0 items-center gap-2">
                      <button
                        type="button"
                        className={btnGhost + " px-2 py-1 text-xs"}
                        onClick={() => setCalendarMonthOffset((v) => v - 1)}
                      >
                        ◀
                      </button>
                      <span className="max-w-[9rem] truncate text-center text-xs font-medium capitalize text-slate-700 sm:max-w-none">{monthLabel}</span>
                      <button
                        type="button"
                        className={btnGhost + " px-2 py-1 text-xs"}
                        onClick={() => setCalendarMonthOffset((v) => v + 1)}
                      >
                        ▶
                      </button>
                    </div>
                  </div>
                  <div className="mb-1 grid grid-cols-7 gap-1 text-center text-[11px] font-semibold text-slate-500">
                    <span>LU</span>
                    <span>MA</span>
                    <span>MI</span>
                    <span>JU</span>
                    <span>VI</span>
                    <span>SA</span>
                    <span>DO</span>
                  </div>
                  <div className="grid grid-cols-7 gap-1">
                    {workCalendar.cells.map((cell, idx) => {
                      if (!cell) {
                        return (
                        <div key={`e-${idx}`} />
                        );
                      }
                      const isPast = cell.isPast || cell.dateISO < todayValue;
                      const hasPublishedFranja = calendarOverrideDays.includes(cell.dateISO);
                      return (
                        <button
                          type="button"
                          key={`d-${idx}`}
                          disabled={isPast}
                          onClick={() => {
                            if (isPast) return;
                            setSpecialDay(cell.dateISO);
                            setSpecialDayMessage("");
                          }}
                          className={`rounded-md border px-1 py-1.5 text-center text-xs ${
                            isPast
                              ? "cursor-not-allowed border-slate-100 bg-slate-100 text-slate-400"
                              : hasPublishedFranja
                                ? "border-emerald-700 bg-emerald-600 text-white"
                                : "border-emerald-300 bg-emerald-100 text-emerald-900"
                          } ${cell.isToday ? "ring-2 ring-emerald-400/70" : ""} ${
                            specialDay === cell.dateISO && !isPast ? "ring-2 ring-blue-400/80" : ""
                          }`}
                          title={
                            isPast
                              ? "Día pasado: no se puede configurar franja"
                              : hasPublishedFranja
                                ? "Este día ya tiene franja publicada para este equipo"
                                : "Puedes abrir franja en este día"
                          }
                        >
                          {cell.day}
                        </button>
                      );
                    })}
                  </div>
                  <p className="mt-2 text-[11px] text-slate-500">
                    Verde claro: día en el que puedes <strong>abrir franja</strong>. Verde oscuro: día que ya tiene{" "}
                    <strong>franja publicada</strong>. Gris: fechas pasadas (sin clic).
                  </p>
                </div>
              </div>
              <div ref={selectedDaySectionRef} className="rounded-lg border border-slate-200 bg-white p-3">
                <p className="text-sm font-semibold text-slate-800">
                  Día seleccionado: {formatLongEsDateFromISO(specialDay)} ({specialDay})
                </p>
                <p className="mb-3 mt-1 text-xs text-slate-500">
                  Haz clic en el calendario para cambiar de día. Aquí puedes ver y modificar la franja de esa fecha.
                </p>
                {specialFranjaRows.length === 0 && (
                  <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
                    <p className="text-xs font-medium text-amber-800">
                      No hay franja horaria para este equipo en este día.
                      {teamHasWeeklyFranjas &&
                      !calendarOverrideDays.includes(specialDay) &&
                      (() => {
                        const [y, m, d] = String(specialDay).split("-").map(Number);
                        const iso =
                          y && m && d ? getIsoWeekday(new Date(y, m - 1, d)) : 0;
                        return !scheduledIsoWeekdays.length || scheduledIsoWeekdays.includes(iso);
                      })()
                        ? " La regla semanal del equipo sigue activa en este día de la semana; aquí puedes definir una excepción solo para esta fecha."
                        : ""}
                      {isSpecialDayPast ? " No se puede agregar porque el día ya pasó." : ""}
                    </p>
                    {!isSpecialDayPast && (
                      <button
                        type="button"
                        className="mt-2 rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-xs font-medium text-amber-900 hover:bg-amber-100"
                        disabled={!specialDayCanEdit}
                        onClick={() => {
                          setSpecialFranjaRows([{ start_local: "08:00", end_local: "11:00" }]);
                          selectedDaySectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
                        }}
                      >
                        Agregar franja en día seleccionado
                      </button>
                    )}
                  </div>
                )}
                {specialFranjaRows.length > 0 && (
                  <FranjaRowsTable
                    rows={specialFranjaRows}
                    inputClass={input}
                    disabled={!specialDayCanEdit}
                    idPrefix="special-franja"
                    onChangeRow={(idx, field, value) => {
                      setSpecialFranjaRows((prev) =>
                        prev.map((r, i) => (i === idx ? { ...r, [field]: value } : r))
                      );
                    }}
                    onRemoveRow={(idx) => setSpecialFranjaRows((prev) => prev.filter((_, i) => i !== idx))}
                  />
                )}
                {!isSpecialDayPast && (
                  <div className="flex flex-wrap gap-2 pt-1">
                    <button
                      type="button"
                      className={btnGhost}
                      disabled={!specialDayCanEdit}
                      onClick={() => setSpecialFranjaRows((prev) => [...prev, { start_local: "09:00", end_local: "10:00" }])}
                    >
                      Añadir franja del día
                    </button>
                    <button
                      type="button"
                      className={btnPrimary}
                      disabled={!specialDayCanEdit || Boolean(specialFranjaValidationError)}
                      onClick={onSaveSpecialDayFranjas}
                    >
                      Guardar franja del día
                    </button>
                    <button type="button" className={btnGhost} disabled={!specialDayCanEdit} onClick={onClearSpecialDayFranjas}>
                      Eliminar franja del día
                    </button>
                  </div>
                )}
                {!specialDayCanEdit && (
                  <p className="mt-2 text-xs font-medium text-rose-700">
                    {isSpecialDayPast
                      ? "No se puede editar ni agregar franjas porque el día ya pasó."
                      : "No se puede editar esta fecha porque ya tiene citas."}
                  </p>
                )}
                {specialDayCanEdit && specialFranjaValidationError && (
                  <p className="mt-2 text-xs font-medium text-rose-700">{specialFranjaValidationError}</p>
                )}
                {specialDayMessage && <p className="mt-2 text-xs font-medium text-emerald-700">{specialDayMessage}</p>}
              </div>
            </form>
            {/* Ocultado por solicitud: mensaje "Turnos agendables ..." */}

            <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50/70 p-4">
              <h3 className="mb-2 text-sm font-semibold text-slate-800">Aplicar franja a grupo de días</h3>
              <p className="mb-3 text-xs text-slate-600">
                Puedes seleccionar un rango de fechas y días de semana para aplicar la misma franja. Los días pasados o con citas se omiten.
              </p>
              <form className="space-y-3" onSubmit={onSaveBulkDateFranjas}>
                <div className="grid gap-2 md:grid-cols-2">
                  <div>
                    <label htmlFor="admin-bulk-start-day" className="mb-1 block text-xs font-medium text-slate-600">Desde</label>
                    <input id="admin-bulk-start-day" type="date" min={todayValue} className={input} value={bulkStartDay} onChange={(e) => setBulkStartDay(e.target.value)} />
                  </div>
                  <div>
                    <label htmlFor="admin-bulk-end-day" className="mb-1 block text-xs font-medium text-slate-600">Hasta</label>
                    <input id="admin-bulk-end-day" type="date" min={bulkStartDay || todayValue} className={input} value={bulkEndDay} onChange={(e) => setBulkEndDay(e.target.value)} />
                  </div>
                </div>
                {/* Se eliminó el selector de “días de la semana del lote”. */}
                <FranjaRowsTable
                  rows={bulkFranjaRows}
                  inputClass={input}
                  idPrefix="bulk-franja"
                  onChangeRow={(idx, field, value) => {
                    setBulkFranjaRows((prev) => prev.map((r, i) => (i === idx ? { ...r, [field]: value } : r)));
                  }}
                  onRemoveRow={(idx) => setBulkFranjaRows((prev) => prev.filter((_, i) => i !== idx))}
                  emptyMessage="Añade al menos una franja con el botón de abajo."
                />
                <div className="flex flex-wrap gap-2 pt-1">
                  <button type="button" className={btnGhost} onClick={() => setBulkFranjaRows((prev) => [...prev, { start_local: "09:00", end_local: "10:00" }])}>
                    Añadir franja lote
                  </button>
                  <button type="submit" className={btnPrimary}>
                    Aplicar a grupo de días
                  </button>
                </div>
                {bulkMessage && <p className="text-xs font-medium text-emerald-700">{bulkMessage}</p>}
              </form>
            </div>
          </div>
        )}

        {isGlobalAdmin && adminTab === "equipo" && (
          <div className="grid gap-4 md:grid-cols-1">
            <div className={card}>
              <h2 className="mb-2 text-lg font-semibold text-slate-900">Alta de personal interno</h2>
              <p className="mb-3 text-xs text-slate-500">
                Admin global (todas las bodegas). Administrador de bodega y Logística pueden tener{" "}
                <strong>una o más bodegas</strong> asignadas. El admin de bodega cancela y modifica citas en sus bodegas;
                Logística coordina citas en las suyas sin configurar franjas.
              </p>
              <form className="flex flex-col gap-2" onSubmit={onCreateUser}>
                <input
                  className={input}
                  placeholder="Documento (solo dígitos)"
                  value={nuDoc}
                  autoComplete="off"
                  inputMode="numeric"
                  pattern="[0-9]{7,10}"
                  maxLength={10}
                  onChange={(e) => setNuDoc(e.target.value.replace(/\D/g, ""))}
                  required
                />
                <input
                  className={input}
                  placeholder="Correo"
                  type="email"
                  value={nuEmail}
                  autoComplete="off"
                  onChange={(e) => setNuEmail(e.target.value)}
                  required
                />
                <input
                  className={input}
                  placeholder="Nombre completo"
                  value={nuName}
                  autoComplete="off"
                  onChange={(e) => setNuName(e.target.value)}
                  required
                />
                <div className="relative overflow-hidden rounded-lg">
                  <input
                    className={input + " pr-11"}
                    placeholder="Contraseña"
                    type={showNuPass ? "text" : "password"}
                    value={nuPass}
                    autoComplete="new-password"
                    onChange={(e) => setNuPass(e.target.value)}
                    required
                    minLength={8}
                  />
                  <PasswordVisibilityButton
                    visible={showNuPass}
                    onToggle={() => setShowNuPass((v) => !v)}
                    label="contraseña"
                  />
                </div>

                <div className="relative overflow-hidden rounded-lg">
                  <input
                    className={input + " pr-11"}
                    placeholder="Confirmar contraseña"
                    type={showNuPassConfirm ? "text" : "password"}
                    value={nuPassConfirm}
                    autoComplete="new-password"
                    onChange={(e) => setNuPassConfirm(e.target.value)}
                    required
                    minLength={8}
                  />
                  <PasswordVisibilityButton
                    visible={showNuPassConfirm}
                    onToggle={() => setShowNuPassConfirm((v) => !v)}
                    label="confirmar contraseña"
                  />
                </div>
                <select
                  className={input}
                  value={nuRoleId}
                  onChange={(e) => {
                    setNuRoleId(e.target.value);
                    const role = internalRolesOnly.find((r) => String(r.id) === e.target.value);
                    if (!roleNeedsWarehouses(role?.name)) setNuWarehouseIds([]);
                  }}
                  required
                >
                  {internalRolesOnly.map((r) => (
                    <option key={r.id} value={r.id}>
                      {ROLE_LABELS[r.name] || r.name}
                    </option>
                  ))}
                </select>
                {roleNeedsWarehouses(nuRoleName) && (
                  <div className="rounded-lg border border-slate-200 bg-slate-50/80 p-3">
                    <p className="mb-2 text-xs font-medium text-slate-700">
                      Bodegas asignadas (una o más)
                    </p>
                    <p className="mb-2 text-[11px] text-slate-500">{warehouseScopeHint(nuRoleName)}</p>
                    <div className="max-h-36 space-y-1 overflow-y-auto rounded-md border border-slate-100 bg-white p-2">
                      {warehouses.map((w) => (
                        <label key={w.id} className="flex items-center gap-2 text-sm text-slate-700">
                          <input
                            type="checkbox"
                            checked={nuWarehouseIds.includes(String(w.id))}
                            onChange={(e) => {
                              const id = String(w.id);
                              setNuWarehouseIds((prev) =>
                                e.target.checked ? [...prev, id] : prev.filter((x) => x !== id)
                              );
                            }}
                          />
                          {w.name}
                        </label>
                      ))}
                    </div>
                    {nuWarehouseIds.length > 0 && (
                      <p className="mt-2 text-[11px] font-medium text-emerald-800">
                        Seleccionadas: {nuWarehouseIds.length} bodega{nuWarehouseIds.length === 1 ? "" : "s"}
                      </p>
                    )}
                    {warehouses.length === 0 && (
                      <p className="text-xs text-slate-500">Crea bodegas antes de asignar este rol.</p>
                    )}
                  </div>
                )}
                <button type="submit" className={btnPrimary}>
                  Crear usuario
                </button>
                {teamMessage && <p className="text-xs font-medium text-emerald-700">{teamMessage}</p>}
              </form>
            </div>
            <div className={`${card} md:col-span-2`}>
              <h3 className="mb-2 text-sm font-semibold text-slate-800">Usuarios internos actuales</h3>
              <div className="mb-3 flex flex-col gap-2">
                <input
                  className={input}
                  placeholder="Filtrar por nombre o correo"
                  value={staffNameFilter}
                  onChange={(e) => setStaffNameFilter(e.target.value)}
                />
                <select className={input} value={staffRoleFilter} onChange={(e) => setStaffRoleFilter(e.target.value)}>
                  <option value="">Todos los roles</option>
                  <option value="Admin">Administrador</option>
                  <option value="AdminBodega">Administrador de bodega</option>
                  <option value="Logistica">Logística</option>
                </select>
              </div>
              <div className="max-h-[34rem] overflow-auto rounded-lg border border-slate-200 bg-white max-lg:min-h-[22rem] max-lg:max-h-[34rem]">
                <table className="w-full min-w-[40rem] border-collapse text-sm">
                  <thead className="sticky top-0 z-[1] border-b border-slate-200 bg-slate-50">
                    <tr>
                      <th
                        scope="col"
                        className="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-600"
                      >
                        Nombre
                      </th>
                      <th
                        scope="col"
                        className="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-600"
                      >
                        Rol
                      </th>
                      <th
                        scope="col"
                        className="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-600"
                      >
                        Bodegas
                      </th>
                      <th
                        scope="col"
                        className="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-600"
                      >
                        Documento
                      </th>
                      <th
                        scope="col"
                        className="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-600"
                      >
                        Correo
                      </th>
                      {isAdmin && (
                        <th
                          scope="col"
                          className="w-40 px-3 py-2.5 text-right text-xs font-semibold uppercase tracking-wide text-slate-600"
                        >
                          Acción
                        </th>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {filteredStaffUsers.length === 0 && (
                      <tr>
                        <td
                          colSpan={isAdmin ? 6 : 5}
                          className="px-3 py-6 text-center text-sm text-slate-500"
                        >
                          No hay usuarios que coincidan con los filtros.
                        </td>
                      </tr>
                    )}
                    {filteredStaffUsers.map((u) => {
                      const warehouseLabel = formatUserWarehousesLabel(u.role_name, u.warehouse_ids, warehouses);
                      if (editingUserId === u.document_id) {
                        return (
                          <tr key={u.document_id} className="border-b border-slate-100 bg-amber-50/40">
                            <td colSpan={isAdmin ? 6 : 5} className="px-3 py-3">
                              <div className="space-y-2">
                                <input
                                  className={input}
                                  value={editUserName}
                                  onChange={(e) => setEditUserName(e.target.value)}
                                  placeholder="Nombre completo"
                                />
                                <input
                                  className={input}
                                  type="email"
                                  value={editUserEmail}
                                  onChange={(e) => setEditUserEmail(e.target.value)}
                                  placeholder="Correo"
                                />
                                <select
                                  className={input}
                                  value={editUserRoleId}
                                  onChange={(e) => {
                                    setEditUserRoleId(e.target.value);
                                    const role = internalRolesOnly.find((r) => String(r.id) === e.target.value);
                                    if (!roleNeedsWarehouses(role?.name)) setEditUserWarehouseIds([]);
                                  }}
                                >
                                  {internalRolesOnly.map((r) => (
                                    <option key={r.id} value={r.id}>
                                      {ROLE_LABELS[r.name] || r.name}
                                    </option>
                                  ))}
                                </select>
                                {roleNeedsWarehouses(editRoleName) && (
                                  <div className="rounded-lg border border-slate-200 bg-white p-3">
                                    <p className="mb-2 text-xs font-medium text-slate-700">
                                      Bodegas asignadas (una o más)
                                    </p>
                                    <p className="mb-2 text-[11px] text-slate-500">{warehouseScopeHint(editRoleName)}</p>
                                    <div className="max-h-36 space-y-1 overflow-y-auto rounded-md border border-slate-100 bg-white p-2">
                                      {warehouses.map((w) => (
                                        <label key={w.id} className="flex items-center gap-2 text-sm text-slate-700">
                                          <input
                                            type="checkbox"
                                            checked={editUserWarehouseIds.includes(String(w.id))}
                                            onChange={(e) => {
                                              const id = String(w.id);
                                              setEditUserWarehouseIds((prev) =>
                                                e.target.checked ? [...prev, id] : prev.filter((x) => x !== id)
                                              );
                                            }}
                                          />
                                          {w.name}
                                        </label>
                                      ))}
                                    </div>
                                    {editUserWarehouseIds.length > 0 && (
                                      <p className="mt-2 text-[11px] font-medium text-emerald-800">
                                        Seleccionadas: {editUserWarehouseIds.length} bodega
                                        {editUserWarehouseIds.length === 1 ? "" : "s"}
                                      </p>
                                    )}
                                  </div>
                                )}
                                <div className="flex flex-wrap gap-2">
                                  <button type="button" className={btnPrimary} onClick={() => onSaveEditUser(u.document_id)}>
                                    Guardar cambios
                                  </button>
                                  <button type="button" className={btnGhost} onClick={onCancelEditUser}>
                                    Cancelar
                                  </button>
                                </div>
                              </div>
                            </td>
                          </tr>
                        );
                      }
                      return (
                        <tr
                          key={u.document_id}
                          className="border-b border-slate-100 last:border-b-0 odd:bg-white even:bg-slate-50/50"
                        >
                          <td className="px-3 py-2.5 align-middle font-medium text-slate-900">{u.full_name}</td>
                          <td className="px-3 py-2.5 align-middle text-slate-700">
                            {ROLE_LABELS[u.role_name] || u.role_name}
                          </td>
                          <td className="px-3 py-2.5 align-middle text-slate-700">{warehouseLabel}</td>
                          <td className="px-3 py-2.5 align-middle tabular-nums text-slate-700">{u.document_id}</td>
                          <td className="px-3 py-2.5 align-middle text-slate-700">{u.email}</td>
                          {isAdmin && (
                            <td className="px-3 py-2.5 align-middle text-right">
                              <div className="flex flex-wrap justify-end gap-2">
                                <button type="button" className={btnGhost} onClick={() => onStartEditUser(u)}>
                                  Editar
                                </button>
                                <button
                                  type="button"
                                  className="rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm font-medium text-rose-700 hover:bg-rose-100"
                                  onClick={() => setConfirmDeleteUserId(u.document_id)}
                                >
                                  Eliminar
                                </button>
                              </div>
                            </td>
                          )}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {isGlobalAdmin && adminTab === "proveedores" && (
          <div className="grid gap-4">
            <div className={card}>
              <h2 className="mb-1 text-lg font-semibold text-slate-900">Proveedores registrados</h2>
              <p className="mb-4 text-xs text-slate-500">
                Total: {providerStats.total} · Activos: {providerStats.activos} · Suspendidos:{" "}
                {providerStats.suspendidos}. Suspende si tiene citas o dudas; elimina solo sin citas. Los suspendidos
                se purgan a los 6 meses (solo queda auditoría).
              </p>
              <div className="mb-4 grid gap-2 md:grid-cols-2">
                <input
                  className={input}
                  placeholder="Filtrar por empresa, correo, contacto o NIT"
                  value={providerFilter}
                  onChange={(e) => setProviderFilter(e.target.value)}
                />
                <select
                  className={input}
                  value={providerStatusFilter}
                  onChange={(e) => setProviderStatusFilter(e.target.value)}
                >
                  <option value="">Todos los estados</option>
                  <option value="activo">Activos</option>
                  <option value="suspendido">Suspendidos</option>
                </select>
              </div>
              {providersMessage && <p className="mb-3 text-xs font-medium text-emerald-700">{providersMessage}</p>}
              <ul className="max-h-[40rem] space-y-2 overflow-y-auto text-sm text-slate-600 max-lg:min-h-[16rem]">
                {filteredProviders.map((p) => (
                  <li key={p.nit} className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-3">
                    {editingProviderNit === p.nit ? (
                      <div className="space-y-2">
                        <input
                          className={input}
                          value={editProviderCompany}
                          onChange={(e) => setEditProviderCompany(e.target.value)}
                          placeholder="Nombre empresa"
                        />
                        <input
                          className={input}
                          type="email"
                          value={editProviderEmail}
                          onChange={(e) => setEditProviderEmail(e.target.value)}
                          placeholder="Correo empresa"
                        />
                        <input
                          className={input}
                          value={editProviderContact}
                          onChange={(e) => setEditProviderContact(e.target.value)}
                          placeholder="Persona responsable"
                        />
                        <input
                          className={input}
                          value={editProviderContactDoc}
                          onChange={(e) => setEditProviderContactDoc(e.target.value.replace(/\D/g, ""))}
                          placeholder="Documento responsable"
                          inputMode="numeric"
                        />
                        <input
                          className={input}
                          value={editProviderDigit}
                          onChange={(e) => setEditProviderDigit(e.target.value.replace(/\D/g, "").slice(0, 1))}
                          placeholder="Dígito verificación"
                          maxLength={1}
                        />
                        <input
                          className={input}
                          type="password"
                          value={editProviderPassword}
                          onChange={(e) => setEditProviderPassword(e.target.value)}
                          placeholder="Nueva contraseña (opcional, mín. 6)"
                          autoComplete="new-password"
                        />
                        <div className="flex flex-wrap gap-2">
                          <button type="button" className={btnPrimary} onClick={() => onSaveEditProvider(p.nit)}>
                            Guardar cambios
                          </button>
                          <button type="button" className={btnGhost} onClick={onCancelEditProvider}>
                            Cancelar
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                        <div className="min-w-0 flex-1 space-y-1">
                          <p className="font-semibold text-slate-900">
                            {p.company_name}{" "}
                            <span
                              className={
                                p.status === "suspendido"
                                  ? "ml-1 rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800"
                                  : "ml-1 rounded bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800"
                              }
                            >
                              {p.status === "suspendido" ? "Suspendido" : "Activo"}
                            </span>
                          </p>
                          <p>
                            NIT {p.nit}-{p.verification_digit} · {p.company_email}
                          </p>
                          <p>
                            Responsable: {p.contact_name} (doc. {p.contact_document})
                          </p>
                          <p className="text-xs text-slate-500">
                            Citas: {p.appointments_count ?? 0} · Último acceso: {formatProviderDate(p.last_login_at)}
                            {p.status === "suspendido" && p.purge_scheduled_at
                              ? ` · Purga programada: ${formatProviderDate(p.purge_scheduled_at)}`
                              : ""}
                          </p>
                          {p.status === "suspendido" && p.suspension_reason && (
                            <p className="text-xs text-amber-800">Motivo: {p.suspension_reason}</p>
                          )}
                        </div>
                        <div className="flex shrink-0 flex-wrap gap-2">
                          <button type="button" className={btnGhost} onClick={() => onStartEditProvider(p)}>
                            Editar
                          </button>
                          {p.status === "suspendido" ? (
                            <button
                              type="button"
                              className={btnPrimary}
                              onClick={() => onReactivateProvider(p.nit)}
                            >
                              Reactivar
                            </button>
                          ) : (
                            <button
                              type="button"
                              className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-900 hover:bg-amber-100"
                              onClick={() => setConfirmSuspendProvider(p.nit)}
                            >
                              Suspender
                            </button>
                          )}
                          <button
                            type="button"
                            className="rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm font-medium text-rose-700 hover:bg-rose-100 disabled:opacity-50"
                            disabled={(p.appointments_count ?? 0) > 0}
                            title={
                              (p.appointments_count ?? 0) > 0
                                ? "Tiene citas: usa Suspender en lugar de eliminar"
                                : "Eliminar registro sin citas"
                            }
                            onClick={() => setConfirmDeleteProviderNit(p.nit)}
                          >
                            Eliminar
                          </button>
                        </div>
                      </div>
                    )}
                  </li>
                ))}
                {filteredProviders.length === 0 && (
                  <li className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-slate-500">
                    No hay proveedores que coincidan con los filtros.
                  </li>
                )}
              </ul>
            </div>
          </div>
        )}

        {(showGlobalAuditPanel || showWarehouseAuditPanel) && (
          <div className={card}>
            <h2 className="mb-2 text-lg font-semibold text-slate-900">Auditoría</h2>
            <p className="mb-3 text-xs text-slate-500">
              {showWarehouseAuditPanel
                ? "Historial de cambios en citas de las bodegas que tienes asignadas (cualquier usuario del sistema)."
                : "Acciones de Admin y Logística sobre citas, usuarios y proveedores."}
            </p>
            <div className="mb-4 grid gap-2 md:grid-cols-2 lg:grid-cols-4">
              {showWarehouseAuditPanel && warehouses.length > 0 && (
                <div>
                  <label htmlFor="audit-filter-warehouse" className="mb-1 block text-xs font-medium text-slate-600">
                    Bodega
                  </label>
                  <select
                    id="audit-filter-warehouse"
                    className={input}
                    value={auditWarehouseFilter}
                    onChange={(e) => setAuditWarehouseFilter(e.target.value)}
                  >
                    <option value="">Todas mis bodegas</option>
                    {warehouses.map((w) => (
                      <option key={w.id} value={String(w.id)}>
                        {w.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <div>
                <label htmlFor="audit-filter-actor" className="mb-1 block text-xs font-medium text-slate-600">Actor</label>
                <select id="audit-filter-actor" className={input} value={auditActorId} onChange={(e) => setAuditActorId(e.target.value)}>
                  <option value="">Todos</option>
                  {(showGlobalAuditPanel ? staffUsersOnly : auditActorOptions).map((u) => (
                    <option key={u.document_id} value={u.document_id}>
                      {u.full_name} ({u.role_name || "—"})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="audit-filter-appointment-id" className="mb-1 block text-xs font-medium text-slate-600">ID cita</label>
                <input
                  id="audit-filter-appointment-id"
                  className={input}
                  placeholder="Ej. 12"
                  inputMode="numeric"
                  value={auditAppointmentId}
                  onChange={(e) => setAuditAppointmentId(e.target.value.replace(/\D/g, ""))}
                />
              </div>
              <div>
                <label htmlFor="audit-filter-text" className="mb-1 block text-xs font-medium text-slate-600">Buscar</label>
                <input
                  id="audit-filter-text"
                  className={input}
                  placeholder="Filtrar por caracteres"
                  value={auditTextFilter}
                  onChange={(e) => setAuditTextFilter(e.target.value)}
                />
              </div>
              <div>
                <label htmlFor="audit-filter-role" className="mb-1 block text-xs font-medium text-slate-600">Rol</label>
                <select id="audit-filter-role" className={input} value={auditRoleFilter} onChange={(e) => setAuditRoleFilter(e.target.value)}>
                  <option value="">Todos los roles</option>
                  {auditRoleOptions.map((role) => (
                    <option key={role} value={role}>
                      {role}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="max-h-[40rem] space-y-2 overflow-y-auto">
              {filteredAuditLogs.length === 0 && <p className="text-sm text-slate-500">Sin registros.</p>}
              {filteredAuditLogs.map((log) => (
                <div key={log.id} className="rounded-lg border border-slate-100 bg-slate-50/80 p-3 text-sm text-slate-700">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <span className="font-medium text-emerald-700">{log.action}</span>
                      {" · "}
                      {log.appointment_id ? `Cita #${log.appointment_id}` : "Gestión de perfiles"}
                      {log.warehouse_name ? (
                        <>
                          {" · "}
                          <span className="text-slate-600">Bodega: {log.warehouse_name}</span>
                        </>
                      ) : null}
                      <br />
                      <span className="text-slate-800">
                        {log.actor_name || "—"}{" "}
                        <span className="text-slate-500">({log.actor_role || log.actor_id})</span>
                      </span>
                      {" · "}
                      {new Date(log.created_at).toLocaleString("es-CO", {
                        dateStyle: "medium",
                        timeStyle: "short",
                        hour12: true,
                      })}
                      {log.description && <span className="mt-1 block text-slate-600">{log.description}</span>}
                      {log.critical_field && (
                        <span className="mt-1 block text-xs text-slate-500">
                          {log.critical_field}: {log.old_value ?? "—"} → {log.new_value ?? "—"}
                        </span>
                      )}
                    </div>
                    <div className="shrink-0">
                      <button
                        type="button"
                        className={btnGhost + " px-3 py-1 text-xs"}
                        onClick={() => toggleExpandedAuditLog(log.id)}
                        aria-expanded={expandedAuditLogIds.map(String).includes(String(log.id))}
                      >
                        {expandedAuditLogIds.map(String).includes(String(log.id)) ? "Ocultar detalles" : "Más detalles"}
                      </button>
                    </div>
                  </div>

                  {expandedAuditLogIds.map(String).includes(String(log.id)) && (
                    <div className="mt-3 rounded-lg border border-slate-200 bg-white/70 p-3 text-xs text-slate-700">
                      <div className="space-y-1.5">
                        <div>
                          <span className="font-semibold text-slate-900">Fecha/hora del evento:</span>{" "}
                          {formatAuditDateTime(log.created_at)}
                        </div>
                        <div>
                          <span className="font-semibold text-slate-900">Actor:</span>{" "}
                          {log.actor_name || "—"}{" "}
                          <span className="text-slate-500">({log.actor_role || log.actor_id || "—"})</span>
                        </div>
                        {log.appointment_id ? (
                          <div>
                            <span className="font-semibold text-slate-900">ID cita:</span> {log.appointment_id}
                          </div>
                        ) : (
                          <div>
                            <span className="font-semibold text-slate-900">Tipo:</span> Gestión de perfiles
                          </div>
                        )}
                        {log.warehouse_name ? (
                          <div>
                            <span className="font-semibold text-slate-900">Bodega:</span> {log.warehouse_name}
                          </div>
                        ) : null}
                        <div>
                          <span className="font-semibold text-slate-900">Acción:</span> {log.action}
                        </div>
                        {log.description ? (
                          <div>
                            <span className="font-semibold text-slate-900">Descripción:</span> {log.description}
                          </div>
                        ) : null}
                        {log.critical_field ? (
                          <div className="pt-1">
                            <span className="font-semibold text-slate-900">Campo crítico:</span>{" "}
                            {log.critical_field}:{" "}
                            {formatAuditCriticalValue(log.critical_field, log.old_value)} →{" "}
                            {formatAuditCriticalValue(log.critical_field, log.new_value)}
                          </div>
                        ) : null}
                        <div className="pt-1 text-slate-500">
                          <span className="font-semibold text-slate-700">Registro:</span> {log.id}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {showConfiguraciones && (
          <div className="grid gap-4 lg:grid-cols-2">
            <div className={card}>
              <h2 className="mb-2 text-lg font-semibold text-slate-900">Datos del perfil</h2>
              <p className="mb-3 text-xs text-slate-500">Actualiza tu nombre y correo de contacto.</p>
              <form className="space-y-2" onSubmit={onSaveProfile}>
                <input
                  className={input}
                  placeholder="Nombre completo"
                  value={profileFullName}
                  onChange={(e) => setProfileFullName(e.target.value)}
                  required
                  minLength={3}
                />
                <input
                  className={input}
                  placeholder="Correo"
                  type="email"
                  value={profileEmail}
                  onChange={(e) => setProfileEmail(e.target.value)}
                  required
                />
                <button type="submit" className={btnPrimary}>
                  Guardar perfil
                </button>
              </form>
            </div>
            <div className={card}>
              <h2 className="mb-2 text-lg font-semibold text-slate-900">Cambiar contraseña</h2>
              <p className="mb-3 text-xs text-slate-500">Usa una contraseña fuerte y confirma el cambio.</p>
              <form className="space-y-2" onSubmit={onChangeProfilePassword}>
                <div className="relative overflow-hidden rounded-lg">
                  <input
                    className={input + " pr-11"}
                    placeholder="Contraseña actual"
                    type={showProfileCurrentPassword ? "text" : "password"}
                    value={profileCurrentPassword}
                    autoComplete="new-password"
                    onChange={(e) => setProfileCurrentPassword(e.target.value)}
                    required
                    minLength={8}
                  />
                  <PasswordVisibilityButton
                    visible={showProfileCurrentPassword}
                    onToggle={() => setShowProfileCurrentPassword((v) => !v)}
                    label="contraseña actual"
                  />
                </div>

                <div className="relative overflow-hidden rounded-lg">
                  <input
                    className={input + " pr-11"}
                    placeholder="Nueva contraseña"
                    type={showProfileNewPassword ? "text" : "password"}
                    value={profileNewPassword}
                    autoComplete="new-password"
                    onChange={(e) => setProfileNewPassword(e.target.value)}
                    required
                    minLength={8}
                  />
                  <PasswordVisibilityButton
                    visible={showProfileNewPassword}
                    onToggle={() => setShowProfileNewPassword((v) => !v)}
                    label="nueva contraseña"
                  />
                </div>

                <div className="relative overflow-hidden rounded-lg">
                  <input
                    className={input + " pr-11"}
                    placeholder="Confirmar nueva contraseña"
                    type={showProfileConfirmPassword ? "text" : "password"}
                    value={profileConfirmPassword}
                    autoComplete="new-password"
                    onChange={(e) => setProfileConfirmPassword(e.target.value)}
                    required
                    minLength={8}
                  />
                  <PasswordVisibilityButton
                    visible={showProfileConfirmPassword}
                    onToggle={() => setShowProfileConfirmPassword((v) => !v)}
                    label="confirmar nueva contraseña"
                  />
                </div>
                <button type="submit" className={btnPrimary}>
                  Actualizar contraseña
                </button>
              </form>
            </div>
            <div className={`${card} lg:col-span-2`}>
              <h2 className="mb-2 text-lg font-semibold text-slate-900">Foto de perfil</h2>
              <p className="mb-3 text-xs text-slate-500">
                Puedes dejarla vacía. Si no tienes foto, se mostrarán las iniciales del nombre y apellido.
              </p>
              <div className="mb-3 flex items-center gap-3">
                {profileData?.photo_url ? (
                  <img
                    src={optimizedProfilePhotoUrl}
                    alt="Foto de perfil"
                    crossOrigin="anonymous"
                    referrerPolicy="no-referrer"
                    loading="lazy"
                    decoding="async"
                    className="h-14 w-14 rounded-full border border-slate-200 object-cover"
                  />
                ) : (
                  <div className="flex h-14 w-14 items-center justify-center rounded-full bg-emerald-500 text-base font-bold text-white">
                    {avatarLetter}
                  </div>
                )}
                <div className="text-xs text-slate-500">{profileData?.role_name || session?.role || ""}</div>
              </div>
              <form className="flex flex-wrap gap-2" onSubmit={onUploadProfilePhoto}>
                <input
                  className={input}
                  type="file"
                  accept="image/*"
                  ref={profilePhotoInputRef}
                  onChange={(e) => setProfilePhotoFile(e.target.files?.[0] || null)}
                />
                <button type="submit" className={btnPrimary}>
                  Subir foto
                </button>
                <button type="button" className={btnGhost} onClick={onRemoveProfilePhoto}>
                  Quitar foto
                </button>
              </form>
              {profilePhotoMessage && <p className="mt-2 text-xs text-slate-600">{profilePhotoMessage}</p>}
            </div>
          </div>
        )}

        {isLogistica && logisticaTab === "citas" && (
          <div className="mb-6 space-y-3" data-tour="section-citas">
            <div className={`${card} p-4`}>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div>
                  <label htmlFor="logistica-citas-range" className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Filtro de citas
                  </label>
                  <select
                    id="logistica-citas-range"
                    name="logistica-citas-range"
                    className={`${input} w-full`}
                    value={citasRange}
                    onChange={(e) => {
                      const nextRange = e.target.value;
                      setCitasRange(nextRange);
                      if (rangeNeedsPeriodSelector(nextRange)) {
                        setCitasPeriod(getDefaultPeriodIndex(nextRange));
                      }
                    }}
                  >
                    <option value="today">Día</option>
                    <option value="week">Semana</option>
                    <option value="biweekly">Quincena</option>
                    <option value="month">Mes</option>
                  </select>
                </div>
                {citasRange === "today" && (
                  <div>
                    <label htmlFor="logistica-citas-day" className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Día
                    </label>
                    <input
                      id="logistica-citas-day"
                      type="date"
                      className={input}
                      value={citasDay}
                      onChange={(e) => setCitasDay(e.target.value)}
                    />
                  </div>
                )}
                {rangeNeedsPeriodSelector(citasRange) && (
                  <div>
                    <label htmlFor="logistica-citas-period" className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                      {getPeriodSelectorLabel(citasRange)}
                    </label>
                    <select
                      id="logistica-citas-period"
                      name="logistica-citas-period"
                      className={`${input} w-full sm:max-w-xs`}
                      value={citasPeriod ?? 1}
                      onChange={(e) => setCitasPeriod(Number(e.target.value))}
                    >
                      {citasPeriodOptions.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
                {citasRange === "month" && (
                  <MonthYearSelects
                    month={citasMonth}
                    year={citasYear}
                    onMonthChange={setCitasMonth}
                    onYearChange={setCitasYear}
                    inputClass={`${input} w-full sm:max-w-xs`}
                    monthId="logistica-citas-month"
                    yearId="logistica-citas-year"
                    labelClassName="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500"
                  />
                )}
                {warehouseFilterControl("logistica-citas-warehouse", "Bodega")}
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
              <div className={card}>
                <p className="text-xs font-medium uppercase text-slate-500">Citas agendadas</p>
                <p className="mt-2 text-3xl font-bold text-slate-900">{citasRangeCount}</p>
                <p className="mt-1 text-xs text-slate-500">Rango: {citasRangeLabel}</p>
              </div>
              <div className={card}>
                <p className="text-xs font-medium uppercase text-slate-500">Citas sin revisión</p>
                <p className="mt-2 text-3xl font-bold text-amber-600">{sinRevisionRangeCount}</p>
                <p className="mt-1 text-xs text-slate-500">Pendientes en el rango</p>
              </div>
              <div className={card}>
                <p className="text-xs font-medium uppercase text-slate-500">Citas ya revisadas</p>
                <p className="mt-2 text-3xl font-bold text-emerald-600">{revisadasRangeCount}</p>
                <p className="mt-1 text-xs text-slate-500">Revisadas en el rango</p>
              </div>
              <div className={card}>
                <p className="text-xs font-medium uppercase text-slate-500">Citas finalizadas</p>
                <p className="mt-2 text-3xl font-bold text-blue-600">{finalizadasRangeCount}</p>
                <p className="mt-1 text-xs text-slate-500">Finalizadas en el rango</p>
              </div>
              <div className={card}>
                <p className="text-xs font-medium uppercase text-slate-500">No presentadas</p>
                <p className="mt-2 text-3xl font-bold text-slate-600">{noPresentadasRangeCount}</p>
                <p className="mt-1 text-xs text-slate-500">No presentadas en el rango</p>
              </div>
              <div className={card}>
                <p className="text-xs font-medium uppercase text-slate-500">Canceladas</p>
                <p className="mt-2 text-3xl font-bold text-rose-600">{canceladasRangeCount}</p>
                <p className="mt-1 text-xs text-slate-500">Canceladas en el rango</p>
              </div>
            </div>
          </div>
        )}

        {showCitasSection && isAdminPanel && (
          <section className="space-y-5" aria-labelledby="admin-citas-title" data-tour="section-citas">
            <h2 id="admin-citas-title" className="sr-only">Gestión de citas</h2>
            <Suspense fallback={appointmentSectionFallback}>
              <AppointmentForm
                onSubmit={onCreate}
                windowsHint=""
                windowsPack={windowsPack}
                warehouses={warehouses}
                warehouseId={selectedWarehouseId}
                onWarehouseChange={setSelectedWarehouseId}
              />
            </Suspense>
          </section>
        )}

        {showBuscarCitasSection && (
          <section aria-labelledby="buscar-citas-title">
            <h2 id="buscar-citas-title" className="sr-only">Buscar citas</h2>
            <div className="mb-3 flex flex-wrap items-center justify-end gap-2">
              <button type="button" className={btnGhost} onClick={onExportStaffXlsx}>
                Descargar Excel (filtros actuales)
              </button>
            </div>
            <div className={`${card} mb-3`}>
              <h3 className="text-sm font-semibold text-slate-900">Ejecuciones de recordatorio</h3>
              <p className="mt-1 text-xs text-slate-500">Últimos recordatorios generados por el scheduler.</p>
              <div className="mt-2 max-h-40 overflow-y-auto">
                {reminders.length === 0 && <p className="text-xs text-slate-500">Sin ejecuciones recientes.</p>}
                {reminders.map((r) => (
                  <div key={r.id} className="border-b border-slate-100 py-1 text-xs text-slate-700">
                    Cita #{r.appointment_id} · {r.status} ·{" "}
                    {new Date(r.executed_at).toLocaleString("es-CO", {
                      dateStyle: "medium",
                      timeStyle: "short",
                      hour12: true,
                    })}
                  </div>
                ))}
              </div>
            </div>
            <Suspense fallback={appointmentSectionFallback}>
              <AppointmentList
                appointments={appointments}
                role={session?.role}
                onReview={onReview}
                onChangeStatus={onChangeStatus}
                onExtend={onExtend}
                onReschedule={onStaffRescheduleAppointment}
                warehouses={warehouses}
                warehouseFilter={filterWarehouseId}
                onWarehouseFilterChange={setFilterWarehouseId}
                viewMode={viewMode}
                onViewModeChange={(mode) => {
                  setViewMode(mode);
                  if (rangeNeedsPeriodSelector(mode)) {
                    setViewPeriod(getDefaultPeriodIndex(mode));
                  }
                }}
                filterDay={filterDay}
                onFilterDayChange={setFilterDay}
                filterPeriod={viewPeriod}
                onFilterPeriodChange={setViewPeriod}
                viewPeriodOptions={viewPeriodOptions}
                filterMonth={filterMonth}
                onFilterMonthChange={setFilterMonth}
                filterYear={filterYear}
                onFilterYearChange={setFilterYear}
              />
            </Suspense>
          </section>
        )}

        {showRevisionSection && (
          <section className="space-y-3" aria-labelledby="revision-citas-title">
            <h2 id="revision-citas-title" className="sr-only">Revisión de citas</h2>
            <div className={`${card} p-4`}>
              <StaffRangeFilterGrid
                inputClass={`${input} w-full`}
                rangeId="review-range-filter"
                rangeLabel="Filtro de revisión"
                range={reviewRange}
                porLabels
                onRangeChange={(e) => {
                  const nextRange = e.target.value;
                  setReviewRange(nextRange);
                  if (nextRange === "today") {
                    setReviewDay((prev) => prev || todayISOInTimeZone());
                  } else {
                    setReviewReferenceDate(new Date());
                  }
                  if (rangeNeedsPeriodSelector(nextRange)) {
                    setReviewPeriod(getDefaultPeriodIndex(nextRange));
                  }
                  setRevisionPinnedAppointment(null);
                }}
                dayId="review-day-filter"
                day={reviewDay}
                onDayChange={(e) => {
                  setReviewDay(e.target.value);
                  setRevisionPinnedAppointment(null);
                }}
                periodId="review-period-filter"
                period={reviewPeriod}
                onPeriodChange={(e) => setReviewPeriod(Number(e.target.value))}
                periodOptions={reviewPeriodOptions}
                month={reviewMonth}
                year={reviewYear}
                onMonthChange={setReviewMonth}
                onYearChange={setReviewYear}
                monthId="review-month-filter"
                yearId="review-year-filter"
                warehouseId={filterWarehouseId}
                warehouseSelectId="revision-citas-warehouse"
                warehouses={warehouses}
                onWarehouseChange={setFilterWarehouseId}
                labelClassName="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-600"
              />
            </div>
            <Suspense fallback={appointmentSectionFallback}>
              <AppointmentList
                appointments={reviewAppointmentsDisplay}
                role={session?.role}
                onReview={onReview}
                onChangeStatus={onChangeStatus}
                onExtend={onExtend}
                onReschedule={onStaffRescheduleAppointment}
                warehouses={warehouses}
                warehouseFilter={filterWarehouseId}
                onWarehouseFilterChange={setFilterWarehouseId}
                reviewMode
                title="Revision de citas"
                emptyMessage="No hay citas para revisar."
                viewMode={viewMode}
                onViewModeChange={setViewMode}
                filterDay={filterDay}
                onFilterDayChange={setFilterDay}
                filterMonth={filterMonth}
                onFilterMonthChange={setFilterMonth}
                filterYear={filterYear}
                onFilterYearChange={setFilterYear}
                openAppointmentId={revisionOpenAppointmentId}
                onOpenAppointmentHandled={() => {
                  setRevisionOpenAppointmentId(null);
                }}
                initialAppointmentIdFilter={
                  revisionOpenAppointmentId != null ? String(revisionOpenAppointmentId) : ""
                }
              />
            </Suspense>
          </section>
        )}

        {showLogisticaHistorial && (
          <div className={card}>
            <h2 className="mb-3 text-lg font-semibold text-slate-900">
              {isLogistica ? "Historial de mis cambios" : "Historial de cambios"}
            </h2>
            <p className="mb-3 text-xs text-slate-500">
              {isLogistica ? "Registro de tus acciones sobre citas." : "Registro de acciones sobre citas."}
            </p>
            <div className="mb-3 w-full sm:max-w-xs">
              <label htmlFor="history-date-filter" className="mb-1 block text-xs font-medium text-slate-600">Filtrar por fecha</label>
              <input id="history-date-filter" type="date" className={input} value={historyDateFilter} onChange={(e) => setHistoryDateFilter(e.target.value)} />
            </div>
            <div className="max-h-[28rem] space-y-2 overflow-y-auto">
              {filteredLogisticaHistoryLogs.length === 0 && <p className="text-sm text-slate-500">Sin registros para la fecha seleccionada.</p>}
              {filteredLogisticaHistoryLogs.map((log) => (
                <div key={log.id} className="rounded-lg border border-slate-100 bg-slate-50/80 p-3 text-sm text-slate-700">
                  <span className="font-medium text-emerald-700">{log.action}</span> ·{" "}
                  {log.appointment_id ? `Cita #${log.appointment_id}` : "Gestión de perfiles"} ·{" "}
                  {new Date(log.created_at).toLocaleString("es-CO", {
                    dateStyle: "medium",
                    timeStyle: "short",
                    hour12: true,
                  })}
                  {(log.actor_name || log.actor_role) && (
                    <span className="mt-1 block text-slate-600">
                      {log.actor_name} ({log.actor_role})
                    </span>
                  )}
                  {log.description && <span className="mt-1 block text-slate-600">{log.description}</span>}
                  {log.critical_field && (
                    <span className="mt-1 block text-xs text-slate-500">
                      {log.critical_field}: {log.old_value ?? "—"} → {log.new_value ?? "—"}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
      {toasts.length > 0 && (
        <div
          className="pointer-events-none fixed bottom-[5.25rem] left-3 right-3 z-50 flex flex-col gap-2 sm:bottom-5 sm:left-auto sm:right-5 sm:max-w-sm"
          role="status"
          aria-live="polite"
          aria-atomic="true"
        >
          {toasts.map((toast) => {
            const isSuccess = toast.type === "success";
            return (
              <div
                key={toast.id}
                className={`pointer-events-auto rounded-xl border px-4 py-3 text-sm shadow-lg ${
                  isSuccess
                    ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                    : "border-red-200 bg-red-50 text-red-800"
                }`}
              >
                <div className="flex items-start gap-3">
                  <p className="flex-1">{toast.message}</p>
                  <button
                    type="button"
                    onClick={() => dismissToast(toast.id)}
                    className={`rounded px-2 py-0.5 transition ${
                      isSuccess ? "text-emerald-700 hover:bg-emerald-100" : "text-red-700 hover:bg-red-100"
                    }`}
                    aria-label="Cerrar notificación"
                  >
                    ×
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
      {isProveedor && (
        <Suspense fallback={null}>
          <ProviderAppointmentNotificationModal
          open={providerNotificationModalOpen}
          appointment={providerNotificationAppointment}
          loading={providerNotificationModalLoading}
          error={providerNotificationModalError}
          cancelReason={
            providerNotificationAppointment
              ? providerCancelReasonById[providerNotificationAppointment.id] || ""
              : ""
          }
          onCancelReasonChange={(value) => {
            const id = providerNotificationAppointment?.id;
            if (!id) return;
            setProviderCancelReasonById((prev) => ({ ...prev, [id]: value }));
          }}
          rescheduleOpen={providerNotificationRescheduleOpen}
          onToggleReschedule={() => setProviderNotificationRescheduleOpen((prev) => !prev)}
          onClose={closeProviderNotificationModal}
          onCancel={onProviderCancelAppointment}
          onReschedule={onProviderRescheduleAppointment}
          loadProviderDayAvailability={fetchProviderDayAvailability}
          inputClass={input}
          buttonClass={btnPrimary}
          rescheduleFallback={appointmentSectionFallback}
          />
        </Suspense>
      )}
    </div>
  );
}
