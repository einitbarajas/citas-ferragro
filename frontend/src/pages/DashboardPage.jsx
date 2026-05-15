import { lazy, Suspense, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  isNarrowPanelTourViewport,
  manualTourBootDelayMs,
  MODULE_TO_NAV_TOUR_ID,
  scrollDashboardSidebarNavItemIntoView,
  TOUR_DASHBOARD_SIDEBAR_SELECTOR,
} from "../guidedTour/panelUtils";
import { getPanelGuidedSteps } from "../guidedTour/panelSteps";
import api, { API_PREFIX, parseApiError, parseApiResponse } from "../api/client";
import AppointmentForm from "../components/AppointmentForm";
import AppointmentList from "../components/AppointmentList";
import AppointmentReschedulePanel from "../components/AppointmentReschedulePanel";
import ConfirmDialog from "../components/ConfirmDialog";
import BrandLogo from "../components/BrandLogo";
import NotificationCenter from "../components/NotificationCenter";
import PasswordVisibilityButton from "../components/PasswordVisibilityButton";
import ThemeToggle from "../components/ThemeToggle";

const GuidedTourDialog = lazy(() => import("../components/GuidedTourDialog"));
import { useAuth } from "../context/AuthContext";
import {
  describeProviderSlotAvailability,
  unwrapProviderDayAvailability,
} from "../utils/providerAvailability";
import { formatReportRangeLabel, getReportRangeBounds } from "../utils/reportRange";

function todayISO() {
  const d = new Date();
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
  { type: "item", id: "horarios", label: "Franjas horarias" },
  { type: "label", text: "Administración" },
  { type: "item", id: "equipo", label: "Equipo (Admin / Logística)" },
  { type: "item", id: "auditoria", label: "Auditoría" },
  { type: "item", id: "configuraciones", label: "Configuraciones" },
];

const card = "rounded-xl border border-slate-200 bg-white p-5 shadow-sm";
const inlay = "rounded-lg border border-slate-200 bg-slate-50/90 p-4";
const TOAST_AUTO_DISMISS_MS = 5000;
const input =
  "w-full rounded-lg border border-slate-400 bg-white px-3 py-2 text-sm text-[#121212] placeholder:text-slate-500 focus:border-[#35783C] focus:outline-none focus:ring-2 focus:ring-[#35783C]/30";
const btnPrimary =
  "min-h-11 rounded-lg bg-[#35783C] px-4 py-2.5 text-sm font-semibold text-white shadow-md shadow-emerald-900/10 transition hover:bg-[#2d6532] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#35783C]/40 disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-60";
const btnGhost =
  "min-h-11 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-[#121212] shadow-sm transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#35783C]/40";
const BULK_ALL_WEEKDAYS = [1, 2, 3, 4, 5, 6, 7];

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

function formatTodayWindowsHint(dayIso, resolvedData, availability = null) {
  const franjas = Array.isArray(resolvedData?.franjas) ? resolvedData.franjas : [];
  const slot = Number(resolvedData?.slot_minutes || availability?.slotMinutes || 90);

  if (franjas.length === 0) {
    return `Hoy (${dayIso}) no tiene franjas configuradas para agendar.`;
  }

  const ranges = franjas.map((w) => `${w.start_local}-${w.end_local}`).join(", ");
  const franjaLine = `Hoy (${dayIso}) la franja habilitada es ${ranges} (turnos cada ${slot} minutos).`;

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
    cells.push({
      day,
      dateISO: `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`,
      isoWeekday: iso,
      enabled: allowedDays.includes(iso),
      isToday: d.toDateString() === new Date().toDateString(),
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
    if (i > 0 && row.start_local <= ordered[i - 1].end_local) {
      return `La ${context} #${i + 1} se cruza con la anterior (debe iniciar después de ${ordered[i - 1].end_local}).`;
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
  const [filterDay, setFilterDay] = useState(todayISO());
  const [filterMonth, setFilterMonth] = useState(new Date().getMonth() + 1);
  const [filterYear, setFilterYear] = useState(new Date().getFullYear());

  const [nuDoc, setNuDoc] = useState("");
  const [nuEmail, setNuEmail] = useState("");
  const [nuName, setNuName] = useState("");
  const [nuPass, setNuPass] = useState("");
  const [nuPassConfirm, setNuPassConfirm] = useState("");
  const [nuRoleId, setNuRoleId] = useState("");
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
  const [providerDayAvailabilityError, setProviderDayAvailabilityError] = useState("");
  const [providerSelectedSlotMinutes, setProviderSelectedSlotMinutes] = useState(90);
  const [providerTimeChoice, setProviderTimeChoice] = useState("");
  const [providerMaterialDescription, setProviderMaterialDescription] = useState("");
  const [providerAppointments, setProviderAppointments] = useState([]);
  const [providerCancelReasonById, setProviderCancelReasonById] = useState({});
  const [providerRescheduleId, setProviderRescheduleId] = useState(null);
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
  const [calendarOverrideDays, setCalendarOverrideDays] = useState([]);
  const [calendarMonthOffset, setCalendarMonthOffset] = useState(0);
  const [analytics, setAnalytics] = useState(null);
  const [auditActorId, setAuditActorId] = useState("");
  const [auditAppointmentId, setAuditAppointmentId] = useState("");
  const [auditTextFilter, setAuditTextFilter] = useState("");
  const [auditRoleFilter, setAuditRoleFilter] = useState("");
  const [historyDateFilter, setHistoryDateFilter] = useState("");
  const [analyticsRange, setAnalyticsRange] = useState("today");
  const [citasRange, setCitasRange] = useState("today");
  const [reviewRange, setReviewRange] = useState("today");
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

  const isAdmin = session?.role === "Admin";
  const isLogistica = session?.role === "Logistica";
  const isProveedor = session?.role === "Proveedor";

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

  const isStaff = isLogistica || isAdmin;

  const internalRolesOnly = roles.filter((r) => r.name === "Admin" || r.name === "Logistica");
  const staffUsersOnly = internalUsers.filter((u) => u.role_name === "Admin" || u.role_name === "Logistica");
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
    const item = ADMIN_NAV.find((x) => x.type === "item" && x.id === adminTab);
    return item?.label || "Panel";
  }, [isProveedor, proveedorTab, isLogistica, logisticaTab, adminTab]);

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
      if (isAdmin) setAdminTab(step.moduleTarget);
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
    if (isAdmin) setAdminTab("citas");
    if (isLogistica) setLogisticaTab("citas");
    if (isProveedor) setProveedorTab("inicio");

    const steps = getPanelGuidedSteps(isAdmin, isLogistica, isProveedor);
    const bootDelayMs = manualTourBootDelayMs();
    window.setTimeout(() => {
      setPanelGuidedSteps(steps);
      setPanelGuidedIndex(0);
      if (!narrow) setPanelTourLayout(true);
      setPanelGuidedOpen(true);
    }, bootDelayMs);
  }, [isAdmin, isLogistica, isProveedor]);

  const loadAppointments = useCallback(async () => {
    if (!session || !authReady || (!isAdmin && !isLogistica)) return;
    const isRevisionTabActive =
      (isAdmin && adminTab === "revision_citas") || (isLogistica && logisticaTab === "revision_citas");
    const requestMode = isRevisionTabActive ? "list" : viewMode;
    const buildParams = (mode) => {
      const params = new URLSearchParams();
      params.set("mode", mode);
      if (mode === "day" && filterDay) {
        params.set("day", filterDay);
      }
      if (mode === "month") {
        params.set("month", String(filterMonth));
        params.set("year", String(filterYear));
      }
      return params;
    };
    try {
      const response = await api.get(`${API_PREFIX}/crud/appointments?${buildParams(requestMode).toString()}`);
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
  }, [session, authReady, viewMode, filterDay, filterMonth, filterYear, isAdmin, isLogistica, adminTab, logisticaTab]);

  const loadLogs = useCallback(async () => {
    if (!session || (!isAdmin && !isLogistica)) return;
    const params = new URLSearchParams();
    if (auditActorId.trim()) {
      params.set("actor_id", auditActorId.trim());
    }
    if (auditAppointmentId.trim()) {
      params.set("appointment_id", auditAppointmentId.trim());
    }
    const response = await api.get(`${API_PREFIX}/crud/change-logs?${params.toString()}`);
    const payload = parseApiResponse(response);
    if (!payload.success) {
      throw new Error(payload.message);
    }
    const inner = payload.data;
    setLogs(inner?.items ?? (Array.isArray(inner) ? inner : []));
  }, [session, auditActorId, auditAppointmentId, isAdmin, isLogistica]);

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

  const loadWindows = useCallback(async () => {
    if (!session) return;
    const response = await api.get(`${API_PREFIX}/crud/appointment-franjas`);
    const payload = parseApiResponse(response);
    if (!payload.success) {
      throw new Error(payload.message);
    }
    setWindowsPack(payload.data || null);
    const f = payload.data?.franjas;
    if (Array.isArray(f) && f.length > 0) {
      setFranjaRows(f.map((w) => ({ start_local: w.start_local, end_local: w.end_local })));
    }
    const today = todayISO();
    const resolvedResponse = await api.get(`${API_PREFIX}/crud/appointment-franjas/resolved?day=${today}`);
    const resolvedPayload = parseApiResponse(resolvedResponse);
    let availability = null;
    if (isProveedor) {
      try {
        const availabilityResponse = await api.get(`${API_PREFIX}/appointments/available-slots?day=${today}`);
        const sourceData = unwrapProviderDayAvailability(availabilityResponse);
        availability = {
          times: Array.isArray(sourceData?.available_times) ? sourceData.available_times : [],
          reason: String(sourceData?.unavailable_reason || "").trim(),
          message: String(sourceData?.unavailable_message || "").trim(),
          minimumNoticeHours: Number(sourceData?.minimum_notice_hours || 24),
          slotMinutes: Number(sourceData?.slot_minutes || 90),
        };
      } catch {
        availability = null;
      }
    }
    if (resolvedPayload.success) {
      setTodayWindowsHint(formatTodayWindowsHint(today, resolvedPayload.data || null, availability));
    } else {
      setTodayWindowsHint("");
    }
  }, [session, isProveedor]);

  const loadSpecialDayWindows = useCallback(
    async (day) => {
      if (!session || !isAdmin || !day) return;
      const response = await api.get(`${API_PREFIX}/crud/appointment-franjas/fecha?day=${day}`);
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
    [session, isAdmin]
  );

  const loadProviderAppointments = useCallback(async () => {
    if (!session || !isProveedor) return;
    const response = await api.get(`${API_PREFIX}/appointments?mode=list`);
    const payload = parseApiResponse(response);
    const raw = payload.success ? payload.data : response?.data;
    if (raw && typeof raw === "object" && !Array.isArray(raw) && Array.isArray(raw.items)) {
      setProviderAppointments(raw.items);
      setError("");
      return;
    }
    if (Array.isArray(raw)) {
      setProviderAppointments(raw);
      setError("");
      return;
    }
    if (!payload.success) {
      throw new Error(payload.message || "No se pudieron cargar tus citas.");
    }
    const inner = payload.data;
    setProviderAppointments(Array.isArray(inner) ? inner : inner?.items ?? []);
    setError("");
  }, [session, isProveedor]);

  const fetchProviderDayAvailability = useCallback(
    async (dayIso, excludeAppointmentId = null) => {
      if (!session || !isProveedor || !dayIso) {
        return { times: [], reason: "", message: "", minimumNoticeHours: 24, slotMinutes: 90 };
      }
      let url = `${API_PREFIX}/appointments/available-slots?day=${dayIso}`;
      if (excludeAppointmentId != null) {
        url += `&exclude_appointment_id=${excludeAppointmentId}`;
      }
      const response = await api.get(url);
      const sourceData = unwrapProviderDayAvailability(response);
      const times = Array.isArray(sourceData?.available_times) ? sourceData.available_times : [];
      return {
        times: Array.from(new Set(times)).sort(),
        reason: String(sourceData?.unavailable_reason || "").trim(),
        message: String(sourceData?.unavailable_message || "").trim(),
        minimumNoticeHours: Number(sourceData?.minimum_notice_hours || 24),
        slotMinutes: Number(sourceData?.slot_minutes || 90),
      };
    },
    [session, isProveedor]
  );

  const loadProviderDayAvailability = useCallback(
    async (dayIso) => {
      if (!session || !isProveedor || !dayIso) return;
      setProviderDayAvailabilityLoading(true);
      setProviderDayAvailabilityError("");
      setProviderSlotUnavailableMessage("");
      setProviderSlotUnavailableReason("");
      try {
        const availability = await fetchProviderDayAvailability(dayIso);
        setProviderSelectedSlots(availability.times);
        setProviderSelectedSlotMinutes(availability.slotMinutes);
        setProviderMinimumNoticeHours(availability.minimumNoticeHours);
        setProviderSlotUnavailableReason(availability.times.length === 0 ? availability.reason : "");
        setProviderSlotUnavailableMessage(availability.times.length === 0 ? availability.message : "");
        setProviderTimeChoice((prev) => (availability.times.includes(prev) ? prev : availability.times[0] || ""));
        setError("");
      } catch (err) {
        setProviderSelectedSlots([]);
        setProviderSlotUnavailableReason("");
        setProviderSlotUnavailableMessage("");
        setProviderDayAvailabilityError(parseApiError(err));
      } finally {
        setProviderDayAvailabilityLoading(false);
      }
    },
    [session, isProveedor, fetchProviderDayAvailability]
  );

  const loadProviderMonthAvailability = useCallback(
    async (targetDate) => {
      if (!session || !isProveedor || !targetDate) return;
      const year = targetDate.getFullYear();
      const month = targetDate.getMonth() + 1;
      const response = await api.get(`${API_PREFIX}/crud/appointment-franjas/fecha/resumen?year=${year}&month=${month}`);
      const payload = parseApiResponse(response);
      if (!payload.success) {
        throw new Error(payload.message);
      }
      const today = todayISO();
      const overrideDays = Array.isArray(payload.data?.override_days) ? payload.data.override_days : [];
      setProviderAvailableDays(overrideDays.filter((d) => String(d) >= today));
    },
    [session, isProveedor]
  );

  const loadCalendarOverrideSummary = useCallback(
    async (targetDate) => {
      if (!session || !isAdmin || !targetDate) return;
      const year = targetDate.getFullYear();
      const month = targetDate.getMonth() + 1;
      const response = await api.get(`${API_PREFIX}/crud/appointment-franjas/fecha/resumen?year=${year}&month=${month}`);
      const payload = parseApiResponse(response);
      if (!payload.success) {
        throw new Error(payload.message);
      }
      setCalendarOverrideDays(Array.isArray(payload.data?.override_days) ? payload.data.override_days : []);
    },
    [session, isAdmin]
  );

  const loadAnalytics = useCallback(async () => {
    if (!session || !isAdmin) return;
    const response = await api.get(`${API_PREFIX}/crud/analytics/summary?range=${analyticsRange}`);
    const payload = parseApiResponse(response);
    if (!payload.success) {
      throw new Error(payload.message);
    }
    setAnalytics(payload.data || null);
  }, [session, isAdmin, analyticsRange]);

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
    setToasts((prev) => [...prev, { id, message, type }]);
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
  }, [viewMode, filterDay, filterMonth, filterYear, pushToast]);

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
        if (isStaff && !isAdmin) tasks.push(loadLogs());
        if (isStaff) tasks.push(loadReminders());
        if (isAdmin) {
          tasks.push(loadRoles());
          tasks.push(loadInternalUsers());
        }
        if (isStaff || isProveedor) tasks.push(loadWindows());
        if (isProveedor) tasks.push(loadProviderAppointments());
        tasks.push(loadProfile());
        await Promise.all(tasks);
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
    loadWindows,
    loadProfile,
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
    if (!session || !authReady) return;
    const refreshData = async () => {
      try {
        if (isStaff) {
          await loadAppointments();
          await loadReminders();
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
    const intervalId = window.setInterval(refreshData, 15000);
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
  ]);

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
  }, [isAdmin, adminTab, loadAnalytics, analyticsRange]);

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
  }, [session, authReady, isStaff, loadAppointments, viewMode, filterDay, filterMonth, filterYear, adminTab, logisticaTab]);

  useEffect(() => {
    if (!isAdmin || adminTab !== "horarios") return;
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
    if (!isAdmin || adminTab !== "horarios") return;
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
  }, [isAdmin, adminTab, calendarMonthOffset, loadCalendarOverrideSummary]);

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
  }, [isProveedor, proveedorTab, providerCalendarMonthOffset, loadProviderMonthAvailability]);

  useEffect(() => {
    if (!isProveedor || proveedorTab !== "inicio") return;
    const run = async () => {
      try {
        await loadProviderDayAvailability(providerSelectedDay);
      } catch (err) {
        setError(parseApiError(err));
      }
    };
    run();
  }, [isProveedor, proveedorTab, providerSelectedDay, session, loadProviderDayAvailability]);

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
    if (!isAdmin || adminTab !== "auditoria") return;
    const run = async () => {
      try {
        await loadLogs();
      } catch (err) {
        setError(parseApiError(err));
      }
    };
    run();
  }, [isAdmin, adminTab, auditActorId, auditAppointmentId, loadLogs]);

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

  useEffect(() => {
    if (internalRolesOnly.length > 0 && nuRoleId === "") {
      setNuRoleId(String(internalRolesOnly[0].id));
    }
  }, [internalRolesOnly, nuRoleId]);

  useEffect(() => {
    // Evita que el navegador/autofill deje valores viejos al entrar al formulario.
    if (isAdmin && adminTab === "equipo") {
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
    const { start, end } = getReportRangeBounds(citasRange);
    return appointments.filter((a) => {
      const dt = new Date(a.start_time);
      return dt >= start && dt < end;
    });
  }, [appointments, citasRange]);
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
  const analyticsRangeLabel = formatReportRangeLabel(analyticsRange);
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
    const roles = new Set(["Admin", "Logistica", "Proveedor"]);
    logs.forEach((log) => {
      if (log?.actor_role) roles.add(log.actor_role);
    });
    return Array.from(roles).sort();
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
    const { start, end } = getReportRangeBounds(reviewRange);
    return appointments.filter((a) => {
      if (a.status !== "sin_revision" && a.status !== "revisado") return false;
      const dt = new Date(a.start_time);
      return dt >= start && dt < end;
    });
  }, [appointments, reviewRange]);

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
      if (isStaff) {
        await loadLogs();
      }
      setSuccess(`Estado de la cita actualizado a ${providerStatusLabel(status)}.`);
    } catch (err) {
      setError(parseApiError(err));
    }
  };

  const onExtend = async (id, extraMinutes = 30) => {
    try {
      setError("");
      setSuccess("");
      await api.patch(`${API_PREFIX}/appointments/${id}/extend`, { extra_minutes: Number(extraMinutes) });
      await loadAppointments();
      await loadReminders();
      if (isStaff) {
        await loadLogs();
      }
      setSuccess("Duración de la cita extendida exitosamente.");
    } catch (err) {
      setError(parseApiError(err));
    }
  };

  const onStaffRescheduleAppointment = async ({ appointmentId, startTime }) => {
    try {
      setError("");
      setSuccess("");
      await api.put(`${API_PREFIX}/crud/appointments/${appointmentId}`, { start_time: startTime });
      await loadAppointments();
      await loadReminders();
      if (isStaff) {
        await loadLogs();
      }
      setSuccess("Cita reprogramada correctamente.");
    } catch (err) {
      const message = parseApiError(err);
      setError(message);
      throw new Error(message);
    }
  };

  const onProviderRescheduleAppointment = async ({ appointmentId, startTime }) => {
    try {
      setError("");
      setSuccess("");
      await api.patch(`${API_PREFIX}/appointments/${appointmentId}/reschedule`, { start_time: startTime });
      setProviderRescheduleId(null);
      await loadProviderAppointments();
      await loadProviderMonthAvailability(providerCalendarBase);
      await loadProviderDayAvailability(providerSelectedDay);
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
      await loadProviderDayAvailability(providerSelectedDay);
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
      await api.post(`${API_PREFIX}/crud/users`, {
        document_id: nuDoc.trim(),
        email: nuEmail.trim(),
        full_name: nuName.trim(),
        password: nuPass,
        role_id: Number(nuRoleId),
      });
      setNuDoc("");
      setNuEmail("");
      setNuName("");
      setNuPass("");
      setNuPassConfirm("");
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
  };

  const onCancelEditUser = () => {
    setEditingUserId("");
    setEditUserName("");
    setEditUserEmail("");
    setEditUserRoleId("");
  };

  const onSaveEditUser = async (documentId) => {
    try {
      setError("");
      setSuccess("");
      setTeamMessage("");
      await api.put(`${API_PREFIX}/crud/users/${documentId}`, {
        full_name: editUserName.trim(),
        email: editUserEmail.trim(),
        role_id: Number(editUserRoleId),
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

  const onSaveFranjas = async (e) => {
    e.preventDefault();
    try {
      setError("");
      setSuccess("");
      const response = await api.put(`${API_PREFIX}/crud/appointment-franjas`, { franjas: franjaRows });
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
      const sortedRows = [...specialFranjaRows].sort((a, b) => String(a.start_local).localeCompare(String(b.start_local)));
      const response = await api.put(`${API_PREFIX}/crud/appointment-franjas/fecha`, {
        day: specialDay,
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
        if (i > 0 && row.start_local <= sortedRows[i - 1].end_local) {
          setError(`La franja de lote #${i + 1} debe iniciar después de ${sortedRows[i - 1].end_local}.`);
          return;
        }
      }
      const response = await api.put(`${API_PREFIX}/crud/appointment-franjas/fecha/lote`, {
        start_day: bulkStartDay,
        end_day: bulkEndDay,
        iso_weekdays: BULK_ALL_WEEKDAYS,
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

  const onClearSpecialDayFranjas = async () => {
    try {
      setError("");
      setSuccess("");
      setSpecialDayMessage("");
      if (!specialDayCanEdit) {
        setError("No puedes editar esta fecha: ya pasó o ya tiene citas.");
        return;
      }
      const response = await api.delete(`${API_PREFIX}/crud/appointment-franjas/fecha?day=${specialDay}`);
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
      const response = await api.put(`${API_PREFIX}/crud/profile/me`, {
        full_name: profileFullName.trim(),
        email: profileEmail.trim(),
      });
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

  const goToBuscarCitas = (mode) => {
    if (mode === "day") {
      setViewMode("day");
      setFilterDay(todayISO());
    } else if (mode === "month") {
      const now = new Date();
      setViewMode("month");
      setFilterMonth(now.getMonth() + 1);
      setFilterYear(now.getFullYear());
    } else {
      setViewMode("list");
    }
    if (isAdmin) {
      setAdminTab("buscar_citas");
    } else if (isLogistica) {
      setLogisticaTab("buscar_citas");
    }
  };

  const handleNotificationNavigate = useCallback(
    (item) => {
      if (!item) return;
      setError("");
      setMobileNavOpen(false);
      if (item.kind === "cita_para_revisar") {
        if (isAdmin) setAdminTab("revision_citas");
        if (isLogistica) setLogisticaTab("revision_citas");
        return;
      }
      if (item.kind === "cita_actualizada" && isProveedor) {
        setProveedorTab("mis_citas");
      }
    },
    [isAdmin, isLogistica, isProveedor]
  );

  const showCitasSection = isStaff && (!isAdmin || adminTab === "citas") && (!isLogistica || logisticaTab === "citas");
  const showBuscarCitasSection = isStaff && (adminTab === "buscar_citas" || (isLogistica && logisticaTab === "buscar_citas"));
  const showRevisionSection = isStaff && (adminTab === "revision_citas" || (isLogistica && logisticaTab === "revision_citas"));
  const showLogisticaHistorial = isLogistica && logisticaTab === "historial";
  const showConfiguraciones =
    (isAdmin && adminTab === "configuraciones") ||
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
  const providerBookedDays = useMemo(() => {
    const set = new Set();
    const tz = String(windowsPack?.timezone || DEFAULT_BUSINESS_TZ);
    providerAppointments.forEach((a) => {
      if (a.status === "cancelado") return;
      const iso = calendarDayISOInTimeZone(a.start_time, tz);
      if (iso) set.add(iso);
    });
    return set;
  }, [providerAppointments, windowsPack?.timezone]);
  const providerCannotScheduleSlot = useMemo(() => {
    if (!providerSelectedDay) return true;
    if (providerDayAvailabilityLoading) return true;
    if (providerBookedDays.has(providerSelectedDay)) return true;
    if (providerSelectedSlots.length === 0) return true;
    if (!providerTimeChoice || !providerSelectedSlots.includes(providerTimeChoice)) return true;
    return false;
  }, [
    providerSelectedDay,
    providerDayAvailabilityLoading,
    providerBookedDays,
    providerSelectedSlots,
    providerTimeChoice,
  ]);
  const providerSlotAvailabilityCopy = useMemo(
    () =>
      describeProviderSlotAvailability({
        loading: providerDayAvailabilityLoading,
        loadError: providerDayAvailabilityError,
        hasExistingAppointment: providerBookedDays.has(providerSelectedDay),
        reason: providerSlotUnavailableReason,
        message: providerSlotUnavailableMessage,
        minimumNoticeHours: providerMinimumNoticeHours,
        selectedDayOpen: providerAvailableDays.includes(providerSelectedDay),
      }),
    [
      providerDayAvailabilityLoading,
      providerDayAvailabilityError,
      providerBookedDays,
      providerSelectedDay,
      providerSlotUnavailableReason,
      providerSlotUnavailableMessage,
      providerMinimumNoticeHours,
      providerAvailableDays,
    ]
  );
  const providerSlotAvailabilityNoticeClass =
    providerSlotAvailabilityCopy.tone === "error"
      ? "border-rose-200 bg-rose-50 text-rose-900"
      : providerSlotAvailabilityCopy.tone === "info"
        ? "border-slate-200 bg-slate-50 text-slate-700"
        : "border-amber-200 bg-amber-50 text-amber-950";

  useEffect(() => {
    if (!isProveedor || !providerSelectedDay) return;
    if (!providerBookedDays.has(providerSelectedDay)) return;
    setProviderTimeChoice("");
  }, [isProveedor, providerBookedDays, providerSelectedDay]);

  useEffect(() => {
    if (!isProveedor || proveedorTab !== "inicio") return;
    const open = providerAvailableDays;
    if (!Array.isArray(open) || open.length === 0) return;
    const sel = providerSelectedDay;
    if (!sel || open.includes(sel) || providerBookedDays.has(sel)) return;
    setProviderSelectedDay(open[0]);
  }, [isProveedor, proveedorTab, providerAvailableDays, providerBookedDays, providerSelectedDay]);

  const onProviderCreateAppointment = useCallback(async () => {
    try {
      setError("");
      setSuccess("");
      if (!providerSelectedDay) {
        setError("Selecciona un día en el calendario.");
        return;
      }
      const tz = String(windowsPack?.timezone || DEFAULT_BUSINESS_TZ);
      const dayBooked = providerAppointments.some((a) => {
        if (a.status === "cancelado") return false;
        return calendarDayISOInTimeZone(a.start_time, tz) === providerSelectedDay;
      });
      if (dayBooked) {
        setError("Ya tienes una cita agendada para este día.");
        return;
      }
      if (
        providerSelectedSlots.length === 0 ||
        !providerTimeChoice ||
        !providerSelectedSlots.includes(providerTimeChoice)
      ) {
        setError("No hay una franja horaria disponible para agendar en esta fecha.");
        return;
      }
      const desc = providerMaterialDescription.trim();
      if (desc.length < 5) {
        setError("Describe qué vas a entregar (mínimo 5 caracteres).");
        return;
      }
      const [y, m, d] = providerSelectedDay.split("-").map(Number);
      const [hh, mm] = providerTimeChoice.split(":").map(Number);
      const localDate = new Date(y, m - 1, d, hh, mm, 0);
      await api.post(`${API_PREFIX}/appointments`, {
        title: "Entrega de material",
        material_description: desc,
        start_time: localDate.toISOString(),
        duration_minutes: 90,
      });
      setProviderMaterialDescription("");
      await loadProviderAppointments();
      await loadProviderMonthAvailability(providerCalendarBase);
      await loadProviderDayAvailability(providerSelectedDay);
      setSuccess("Cita agendada exitosamente.");
    } catch (err) {
      setError(parseApiError(err));
    }
  }, [
    providerSelectedDay,
    providerAppointments,
    providerSelectedSlots,
    providerTimeChoice,
    providerMaterialDescription,
    providerCalendarBase,
    windowsPack?.timezone,
    loadProviderAppointments,
    loadProviderMonthAvailability,
    loadProviderDayAvailability,
  ]);

  const providerAppointmentsSorted = useMemo(
    () => [...providerAppointments].sort((a, b) => new Date(b.start_time).getTime() - new Date(a.start_time).getTime()),
    [providerAppointments]
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
          <p className="text-[11px] text-slate-600">Panel {isAdmin ? "administrador" : isLogistica ? "logística" : "proveedor"}</p>
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

        {isAdmin &&
          ADMIN_NAV.map((entry, idx) =>
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
      <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">{saludoHorario()}</h1>
      <p className="mt-2 max-w-2xl text-sm text-slate-600">
        {isAdmin &&
          "Gestiona citas de entrega, franjas horarias, equipo interno y auditoría desde un solo panel."}
        {isLogistica && "Coordina citas con proveedores y revisa el historial de cambios."}
        {isProveedor && "Consulta información de tu cuenta. Para nuevas citas, contacta a logística o usa los canales acordados."}
      </p>
    </header>
  );

  const citasRangeLabel = formatReportRangeLabel(citasRange);

  const quickActions =
    isAdmin &&
    adminTab === "citas" && (
      <div className="mb-6 space-y-3">
        <div className={`${card} p-4`}>
          <label htmlFor="admin-citas-range" className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
            Filtro de citas
          </label>
          <select
            id="admin-citas-range"
            name="admin-citas-range"
            className={`${input} w-full sm:max-w-xs`}
            value={citasRange}
            onChange={(e) => setCitasRange(e.target.value)}
          >
            <option value="today">Día</option>
            <option value="week">Semana</option>
            <option value="biweekly">Quincena</option>
            <option value="month">Mes</option>
          </select>
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
          <button type="button" className={btnGhost} onClick={() => setAdminTab("analitica")}>
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
        aria-label="Contenido del panel"
        className={`w-full px-4 py-6 pb-[max(12rem,calc(10rem+env(safe-area-inset-bottom,0px)))] sm:px-5 lg:min-h-0 lg:flex-1 lg:overflow-y-auto lg:overscroll-y-contain lg:px-10 lg:py-8 lg:pb-8 ${isProveedor ? "space-y-5" : ""}`}
      >
        <div className="mb-4 rounded-xl border border-slate-200 bg-white px-3 py-2 shadow-sm lg:hidden">
          <div className="flex items-center justify-between gap-3">
            <BrandLogo className="h-7 w-auto shrink-0" protectedArea={false} />
            <div className="flex shrink-0 flex-nowrap items-center gap-1.5">
              <NotificationCenter compact onNavigate={handleNotificationNavigate} />
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
          <p className="mt-1 text-[11px] font-medium uppercase tracking-wide text-slate-500">{activeNavLabel}</p>
        </div>
        <div className="mb-4 hidden flex-nowrap items-center justify-end gap-2 lg:flex">
          <NotificationCenter onNavigate={handleNotificationNavigate} />
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
        {quickActions}
        {accionesRapidasCitas}

        {isProveedor && proveedorTab === "inicio" && (
          <section className="space-y-4" aria-labelledby="proveedor-inicio-title" data-tour="section-proveedor-inicio">
            <header className="rounded-xl border border-emerald-100 bg-white p-5 shadow-sm">
              <p className="text-xs font-medium uppercase tracking-wide text-emerald-600">Proveedor</p>
              <h1 id="proveedor-inicio-title" className="mt-1 text-2xl font-bold tracking-tight text-slate-900">{saludoHorario()}</h1>
              <p className="mt-2 text-sm text-slate-600">
                Solo puedes agendar en fechas en las que la empresa habilitó franja en el calendario (días en verde claro). La franja semanal general no habilita el día hasta que se abra por fecha.
              </p>
            </header>
            <div className={card}>
              <p className="text-xs font-medium uppercase text-slate-500">Franja vigente</p>
              <p className="mt-2 text-sm text-slate-700">{todayWindowsHint || windowsPack?.hint || "Sin detalle disponible por ahora."}</p>
            </div>
            <div className={card}>
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <p className="min-w-0 text-xs font-medium uppercase text-slate-500">Días con franja abierta (empresa)</p>
                <div className="flex shrink-0 items-center gap-2">
                  <button type="button" className={btnGhost + " px-2 py-1 text-xs"} onClick={() => setProviderCalendarMonthOffset((v) => v - 1)} aria-label="Ir al mes anterior del calendario">
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
                  const canPickDay =
                    providerAvailableDays.includes(cell.dateISO) || providerBookedDays.has(cell.dateISO);
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
                          ? "cursor-not-allowed border-slate-100 bg-slate-50 text-slate-300"
                          : providerBookedDays.has(cell.dateISO)
                            ? "border-emerald-700 bg-emerald-600 text-white"
                            : providerAvailableDays.includes(cell.dateISO)
                              ? "border-emerald-300 bg-emerald-100 text-emerald-900"
                              : "border-slate-200 bg-white text-slate-400"
                      } ${providerSelectedDay === cell.dateISO ? "ring-2 ring-blue-400/80" : ""}`}
                      title={
                        !canPickDay
                          ? "Sin franja abierta este día: la empresa no habilitó citas en esta fecha"
                          : providerBookedDays.has(cell.dateISO)
                            ? "Ya tienes cita ese día"
                            : "Franja habilitada: puedes agendar"
                      }
                    >
                      {cell.day}
                    </button>
                  );
                })}
              </div>
              <p className="mt-2 text-[11px] text-slate-600">
                Verde claro: la empresa abrió franja ese día. Blanco: sin franja (no se puede elegir). Verde oscuro: ya tienes cita.
              </p>
            </div>
            <div className={card}>
              <p className="text-xs font-medium uppercase text-slate-500">Disponibilidad del día</p>
              <p className="mt-1 text-xs text-slate-600">{formatLongEsDateFromISO(providerSelectedDay)} ({providerSelectedDay})</p>
              {providerCannotScheduleSlot && providerSlotAvailabilityCopy.title && (
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
                <div>
                  <label className="mb-1 block text-xs font-medium text-slate-600">Hora disponible</label>
                  <select
                    className={input}
                    value={providerTimeChoice}
                    onChange={(e) => setProviderTimeChoice(e.target.value)}
                    disabled={providerCannotScheduleSlot}
                  >
                    {providerSelectedSlots.length === 0 ? (
                      <option value="">{providerSlotAvailabilityCopy.optionLabel}</option>
                    ) : (
                      providerSelectedSlots.map((h) => (
                        <option key={h} value={h}>
                          {h}
                        </option>
                      ))
                    )}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-slate-600">Intervalo</label>
                  <div className={input + " bg-slate-50"}>{providerSelectedSlotMinutes} minutos</div>
                </div>
              </div>
              <div className="mt-2">
                <label className="mb-1 block text-xs font-medium text-slate-600">Descripción de lo que vas a entregar</label>
                <textarea
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
              >
                Agendar cita
              </button>
            </div>
          </section>
        )}

        {isProveedor && proveedorTab === "mis_citas" && (
          <div className="space-y-4">
            <header className="rounded-xl border border-emerald-100 bg-white p-5 shadow-sm">
              <p className="text-xs font-medium uppercase tracking-wide text-emerald-600">Proveedor</p>
              <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">Mis citas</h1>
              <p className="mt-2 text-sm text-slate-600">Consulta tus citas agendadas, reprográmalas o cancélalas cuando aplique.</p>
            </header>
            <div className={card}>
              <p className="text-xs font-medium uppercase text-slate-500">Mis citas</p>
              <div className="mt-2 space-y-2">
                {providerAppointmentsSorted.length === 0 && <p className="text-sm text-slate-500">Aún no tienes citas agendadas.</p>}
                {providerAppointmentsSorted.map((a) => (
                  <div key={a.id} className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
                    <p className="break-words text-sm font-medium text-slate-800">Cita #{a.id} - {new Date(a.start_time).toLocaleString()}</p>
                    <p className="text-xs text-slate-600">Estado: {providerStatusLabel(a.status)}</p>
                    <p className="text-xs text-slate-600">Descripción: {a.material_description}</p>
                    {a.status !== "cancelado" && a.status !== "finalizada" && a.status !== "no_presentada" && (
                      <div className="mt-2 space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          {(a.status === "sin_revision" || a.status === "revisado") && (
                            <button
                              type="button"
                              className="rounded-lg border border-[#35783C] bg-white px-3 py-2 text-xs font-semibold text-[#35783C] hover:bg-emerald-50"
                              onClick={() =>
                                setProviderRescheduleId((prev) => (prev === a.id ? null : a.id))
                              }
                            >
                              {providerRescheduleId === a.id ? "Cerrar reprogramación" : "Cambiar día y hora"}
                            </button>
                          )}
                          <input
                            className={input + " w-full sm:max-w-md"}
                            placeholder="Motivo de cancelación"
                            value={providerCancelReasonById[a.id] || ""}
                            onChange={(e) => setProviderCancelReasonById((prev) => ({ ...prev, [a.id]: e.target.value }))}
                          />
                          <button
                            type="button"
                            className="rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-xs font-semibold text-rose-700 hover:bg-rose-100"
                            onClick={() => onProviderCancelAppointment(a.id)}
                          >
                            Cancelar cita
                          </button>
                        </div>
                        {providerRescheduleId === a.id && (
                          <AppointmentReschedulePanel
                            appointment={a}
                            variant="provider"
                            inputClass={input}
                            buttonClass={btnPrimary}
                            loadProviderDayAvailability={fetchProviderDayAvailability}
                            onReschedule={onProviderRescheduleAppointment}
                          />
                        )}
                      </div>
                    )}
                  </div>
                ))}
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
              <div className="mt-2 space-y-2">
                {providerHistoryAppointments.length === 0 && <p className="text-sm text-slate-500">No tienes historial todavía.</p>}
                {providerHistoryAppointments.map((a) => (
                  <div key={a.id} className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
                    <p className="break-words text-sm font-medium text-slate-800">Cita #{a.id} - {new Date(a.start_time).toLocaleString()}</p>
                    <p className="text-xs text-slate-600">Estado: {providerStatusLabel(a.status)}</p>
                    <p className="text-xs text-slate-600">Descripción: {a.material_description}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {isAdmin && adminTab === "analitica" && (
          <div className={card}>
            <h2 className="mb-4 text-lg font-semibold text-slate-900">Analítica</h2>
            <div className="mb-4 w-full sm:max-w-xs">
              <label htmlFor="analytics-range-filter" className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-600">
                Filtro
              </label>
              <select
                id="analytics-range-filter"
                name="analytics-range-filter"
                className={`${input} w-full`}
                value={analyticsRange}
                onChange={(e) => setAnalyticsRange(e.target.value)}
              >
                <option value="today">Por día</option>
                <option value="week">Por semana</option>
                <option value="biweekly">Por quincena</option>
                <option value="month">Por mes</option>
              </select>
            </div>
            {!analytics && <p className="text-sm text-slate-500">Cargando…</p>}
            {analytics && (
              <div className="grid gap-4 md:grid-cols-3">
                <div className={inlay + " md:col-span-1"}>
                  <p className="text-xs font-medium uppercase text-slate-500">Citas revisadas ({analyticsRangeLabel})</p>
                  <p className="mt-2 text-2xl font-bold text-emerald-600">{revisadasRangeValue}</p>
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
                  <p className="text-xs font-medium uppercase text-slate-500">Citas por día de la semana</p>
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
                  <p className="text-xs font-medium uppercase text-slate-500">Diagrama de barras por estado (día actual)</p>
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

        {isAdmin && adminTab === "horarios" && (
          <div className={card}>
            <h2 className="mb-2 text-lg font-semibold text-slate-900">Franjas horarias permitidas</h2>
            <p className="mb-4 text-xs text-slate-600">
              Solo el administrador define en qué horas locales (zona {windowsPack?.timezone || "America/Bogota"}) se puede{" "}
              <strong className="text-slate-800">iniciar</strong> una cita. Los turnos se habilitan cada{" "}
              <strong className="text-slate-800">1 hora y 30 minutos</strong> desde el inicio de cada franja (ej.: 08:00,
              09:30, 11:00).
            </p>
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
                    {workCalendar.cells.map((cell, idx) =>
                      cell ? (
                        <button
                          type="button"
                          key={`d-${idx}`}
                          onClick={() => {
                            setSpecialDay(cell.dateISO);
                            setSpecialDayMessage("");
                          }}
                          className={`rounded-md border px-1 py-1.5 text-center text-xs ${
                            calendarOverrideDays.includes(cell.dateISO)
                              ? "border-emerald-500 bg-emerald-500 text-white"
                              : cell.enabled
                                ? "border-emerald-300 bg-emerald-100 text-emerald-900"
                                : "border-slate-200 bg-white text-slate-500"
                          } ${cell.isToday ? "ring-2 ring-emerald-400/70" : ""} ${
                            specialDay === cell.dateISO ? "ring-2 ring-blue-400/80" : ""
                          }`}
                          title={
                            calendarOverrideDays.includes(cell.dateISO)
                              ? "Día con franja especial (clic para editar)"
                              : cell.enabled
                                ? "Día con franja semanal (clic para gestionar)"
                                : "Día no habilitado (clic para gestionar)"
                          }
                        >
                          {cell.day}
                        </button>
                      ) : (
                        <div key={`e-${idx}`} />
                      )
                    )}
                  </div>
                  <p className="mt-2 text-[11px] text-slate-500">
                    Verde fuerte: franja especial por fecha. Verde claro: día habilitado por regla semanal.
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
                      No hay franja horaria para este día.
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
                {specialFranjaRows.map((row, idx) => (
                  <div key={`selected-${idx}`} className="mb-2 flex flex-wrap items-center gap-2">
                    <span className="text-sm text-slate-600">De</span>
                    <input
                      type="time"
                      className={input + " w-auto"}
                      value={row.start_local.length === 5 ? row.start_local : row.start_local.slice(0, 5)}
                      disabled={!specialDayCanEdit}
                      onChange={(e) => {
                        const v = e.target.value;
                        setSpecialFranjaRows((prev) => prev.map((r, i) => (i === idx ? { ...r, start_local: v } : r)));
                      }}
                      required
                    />
                    <span className="text-sm text-slate-600">a</span>
                    <input
                      type="time"
                      className={input + " w-auto"}
                      value={row.end_local.length === 5 ? row.end_local : row.end_local.slice(0, 5)}
                      disabled={!specialDayCanEdit}
                      onChange={(e) => {
                        const v = e.target.value;
                        setSpecialFranjaRows((prev) => prev.map((r, i) => (i === idx ? { ...r, end_local: v } : r)));
                      }}
                      required
                    />
                    <button
                      type="button"
                      className="text-xs text-red-600 underline hover:text-red-700 disabled:opacity-40"
                      disabled={!specialDayCanEdit}
                      onClick={() => setSpecialFranjaRows((prev) => prev.filter((_, i) => i !== idx))}
                    >
                      Quitar
                    </button>
                  </div>
                ))}
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
            {windowsPack?.hint && <p className="mt-3 text-xs text-slate-500">{windowsPack.hint}</p>}

            <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50/70 p-4">
              <h3 className="mb-2 text-sm font-semibold text-slate-800">Aplicar franja a grupo de días</h3>
              <p className="mb-3 text-xs text-slate-600">
                Puedes seleccionar un rango de fechas y días de semana para aplicar la misma franja. Los días pasados o con citas se omiten.
              </p>
              <form className="space-y-3" onSubmit={onSaveBulkDateFranjas}>
                <div className="grid gap-2 md:grid-cols-2">
                  <div>
                    <label className="mb-1 block text-xs font-medium text-slate-600">Desde</label>
                    <input type="date" min={todayValue} className={input} value={bulkStartDay} onChange={(e) => setBulkStartDay(e.target.value)} />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-slate-600">Hasta</label>
                    <input type="date" min={bulkStartDay || todayValue} className={input} value={bulkEndDay} onChange={(e) => setBulkEndDay(e.target.value)} />
                  </div>
                </div>
                <p className="text-xs text-slate-600">Este lote aplica a todos los días dentro del rango seleccionado.</p>
                {bulkFranjaRows.map((row, idx) => (
                  <div key={`bulk-row-${idx}`} className="flex flex-wrap items-center gap-2">
                    <span className="text-sm text-slate-600">De</span>
                    <input
                      type="time"
                      className={input + " w-auto"}
                      value={row.start_local.length === 5 ? row.start_local : row.start_local.slice(0, 5)}
                      onChange={(e) => {
                        const v = e.target.value;
                        setBulkFranjaRows((prev) => prev.map((r, i) => (i === idx ? { ...r, start_local: v } : r)));
                      }}
                      required
                    />
                    <span className="text-sm text-slate-600">a</span>
                    <input
                      type="time"
                      className={input + " w-auto"}
                      value={row.end_local.length === 5 ? row.end_local : row.end_local.slice(0, 5)}
                      onChange={(e) => {
                        const v = e.target.value;
                        setBulkFranjaRows((prev) => prev.map((r, i) => (i === idx ? { ...r, end_local: v } : r)));
                      }}
                      required
                    />
                    <button type="button" className="text-xs text-red-600 underline hover:text-red-700" onClick={() => setBulkFranjaRows((prev) => prev.filter((_, i) => i !== idx))}>
                      Quitar
                    </button>
                  </div>
                ))}
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

        {isAdmin && adminTab === "equipo" && (
          <div className="grid gap-4 md:grid-cols-1">
            <div className={card}>
              <h2 className="mb-2 text-lg font-semibold text-slate-900">Alta Admin o Logística</h2>
              <p className="mb-3 text-xs text-slate-500">Solo roles Admin o Logistica.</p>
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
                <select className={input} value={nuRoleId} onChange={(e) => setNuRoleId(e.target.value)} required>
                  {internalRolesOnly.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </select>
                <button type="submit" className={btnPrimary}>
                  Crear usuario
                </button>
                {teamMessage && <p className="text-xs font-medium text-emerald-700">{teamMessage}</p>}
              </form>
            </div>
            <div className={`${card} md:col-span-2`}>
              <h3 className="mb-2 text-sm font-semibold text-slate-800">Usuarios internos actuales</h3>
              <div className="mb-3 grid gap-2 md:grid-cols-2">
                <input
                  className={input}
                  placeholder="Filtrar por nombre o correo"
                  value={staffNameFilter}
                  onChange={(e) => setStaffNameFilter(e.target.value)}
                />
                <select className={input} value={staffRoleFilter} onChange={(e) => setStaffRoleFilter(e.target.value)}>
                  <option value="">Todos los roles</option>
                  <option value="Admin">Admin</option>
                  <option value="Logistica">Logística</option>
                </select>
              </div>
              <ul className="max-h-48 space-y-1 overflow-y-auto text-sm text-slate-600 max-lg:min-h-[22rem] max-lg:max-h-[32rem]">
                {filteredStaffUsers.map((u) => (
                  <li key={u.document_id} className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
                    {editingUserId === u.document_id ? (
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
                        <select className={input} value={editUserRoleId} onChange={(e) => setEditUserRoleId(e.target.value)}>
                          {internalRolesOnly.map((r) => (
                            <option key={r.id} value={r.id}>
                              {r.name}
                            </option>
                          ))}
                        </select>
                        <div className="flex gap-2">
                          <button type="button" className={btnPrimary} onClick={() => onSaveEditUser(u.document_id)}>
                            Guardar cambios
                          </button>
                          <button type="button" className={btnGhost} onClick={onCancelEditUser}>
                            Cancelar
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        <span className="min-w-0 break-words text-sm">
                          {u.full_name} — {u.role_name} — doc. {u.document_id} — {u.email}
                        </span>
                        {isAdmin && (
                          <div className="flex shrink-0 flex-wrap gap-2">
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
                        )}
                      </div>
                    )}
                  </li>
                ))}
                {filteredStaffUsers.length === 0 && (
                  <li className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-slate-500">
                    No hay usuarios que coincidan con los filtros.
                  </li>
                )}
              </ul>
            </div>
          </div>
        )}

        {isAdmin && adminTab === "auditoria" && (
          <div className={card}>
            <h2 className="mb-2 text-lg font-semibold text-slate-900">Auditoría</h2>
            <p className="mb-3 text-xs text-slate-500">Acciones de Admin y Logística sobre citas, usuarios y proveedores.</p>
            <div className="mb-4 grid gap-2 md:grid-cols-2 lg:grid-cols-4">
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">Actor</label>
                <select className={input} value={auditActorId} onChange={(e) => setAuditActorId(e.target.value)}>
                  <option value="">Todos</option>
                  {staffUsersOnly.map((u) => (
                    <option key={u.document_id} value={u.document_id}>
                      {u.full_name} ({u.role_name})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">ID cita</label>
                <input
                  className={input}
                  placeholder="Ej. 12"
                  inputMode="numeric"
                  value={auditAppointmentId}
                  onChange={(e) => setAuditAppointmentId(e.target.value.replace(/\D/g, ""))}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">Buscar</label>
                <input
                  className={input}
                  placeholder="Filtrar por caracteres"
                  value={auditTextFilter}
                  onChange={(e) => setAuditTextFilter(e.target.value)}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">Rol</label>
                <select className={input} value={auditRoleFilter} onChange={(e) => setAuditRoleFilter(e.target.value)}>
                  <option value="">Todos los roles</option>
                  {auditRoleOptions.map((role) => (
                    <option key={role} value={role}>
                      {role}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="max-h-[28rem] space-y-2 overflow-y-auto">
              {filteredAuditLogs.length === 0 && <p className="text-sm text-slate-500">Sin registros.</p>}
              {filteredAuditLogs.map((log) => (
                <div key={log.id} className="rounded-lg border border-slate-100 bg-slate-50/80 p-3 text-sm text-slate-700">
                  <span className="font-medium text-emerald-700">{log.action}</span>
                  {" · "}
                  {log.appointment_id ? `Cita #${log.appointment_id}` : "Gestión de perfiles"}
                  <br />
                  <span className="text-slate-800">
                    {log.actor_name || "—"} <span className="text-slate-500">({log.actor_role || log.actor_id})</span>
                  </span>
                  {" · "}
                  {new Date(log.created_at).toLocaleString()}
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

        {showConfiguraciones && (
          <div className="grid gap-4 lg:grid-cols-2">
            <div className={card}>
              <h2 className="mb-2 text-lg font-semibold text-slate-900">Datos del perfil</h2>
              <p className="mb-3 text-xs text-slate-500">Actualiza nombre y correo de tu cuenta.</p>
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
              <label htmlFor="logistica-citas-range" className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                Filtro de citas
              </label>
              <select
                id="logistica-citas-range"
                name="logistica-citas-range"
                className={`${input} w-full sm:max-w-xs`}
                value={citasRange}
                onChange={(e) => setCitasRange(e.target.value)}
              >
                <option value="today">Día</option>
                <option value="week">Semana</option>
                <option value="biweekly">Quincena</option>
                <option value="month">Mes</option>
              </select>
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

        {showCitasSection && isAdmin && (
          <section className="space-y-5" aria-labelledby="admin-citas-title" data-tour="section-citas">
            <h2 id="admin-citas-title" className="sr-only">Gestión de citas</h2>
            <AppointmentForm onSubmit={onCreate} windowsHint={windowsPack?.hint || ""} windowsPack={windowsPack} />
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
                    Cita #{r.appointment_id} · {r.status} · {new Date(r.executed_at).toLocaleString()}
                  </div>
                ))}
              </div>
            </div>
            <AppointmentList
              appointments={appointments}
              role={session?.role}
              onReview={onReview}
              onChangeStatus={onChangeStatus}
              onExtend={onExtend}
              onReschedule={onStaffRescheduleAppointment}
              viewMode={viewMode}
              onViewModeChange={setViewMode}
              filterDay={filterDay}
              onFilterDayChange={setFilterDay}
              filterMonth={filterMonth}
              onFilterMonthChange={setFilterMonth}
              filterYear={filterYear}
              onFilterYearChange={setFilterYear}
            />
          </section>
        )}

        {showRevisionSection && (
          <section className="space-y-3" aria-labelledby="revision-citas-title">
            <h2 id="revision-citas-title" className="sr-only">Revisión de citas</h2>
            <div className={`${card} p-4`}>
              <label htmlFor="review-range-filter" className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-600">
                Filtro de revisión
              </label>
              <select
                id="review-range-filter"
                name="review-range-filter"
                className={`${input} w-full sm:max-w-xs`}
                value={reviewRange}
                onChange={(e) => setReviewRange(e.target.value)}
              >
                <option value="today">Por día</option>
                <option value="week">Por semana</option>
                <option value="biweekly">Por quincena</option>
                <option value="month">Por mes</option>
              </select>
            </div>
            <AppointmentList
              appointments={reviewAppointments}
              role={session?.role}
              onReview={onReview}
              onChangeStatus={onChangeStatus}
              onExtend={onExtend}
              onReschedule={onStaffRescheduleAppointment}
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
            />
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
              <label className="mb-1 block text-xs font-medium text-slate-600">Filtrar por fecha</label>
              <input type="date" className={input} value={historyDateFilter} onChange={(e) => setHistoryDateFilter(e.target.value)} />
            </div>
            <div className="max-h-[28rem] space-y-2 overflow-y-auto">
              {filteredLogisticaHistoryLogs.length === 0 && <p className="text-sm text-slate-500">Sin registros para la fecha seleccionada.</p>}
              {filteredLogisticaHistoryLogs.map((log) => (
                <div key={log.id} className="rounded-lg border border-slate-100 bg-slate-50/80 p-3 text-sm text-slate-700">
                  <span className="font-medium text-emerald-700">{log.action}</span> ·{" "}
                  {log.appointment_id ? `Cita #${log.appointment_id}` : "Gestión de perfiles"} ·{" "}
                  {new Date(log.created_at).toLocaleString()}
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
    </div>
  );
}
