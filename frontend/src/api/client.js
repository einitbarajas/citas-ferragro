import axios from "axios";
import {
  AUTH_EXPIRED_EVENT,
  clearAccessToken as resetAccessToken,
  getAccessToken,
  setAccessToken,
} from "./auth-token";

export { AUTH_EXPIRED_EVENT, getAccessToken, setAccessToken };

/** Versión del API en el servidor (routers montados en `/api` y `/api/v1`). */
export const API_PREFIX = (import.meta.env.VITE_API_PREFIX || "/api/v1").trim();

/**
 * - Con `npm run dev`: baseURL vacío → las peticiones van al mismo host/puerto del front (p. ej. :2711) y
 *   Vite reenvía `/api` y `/health` al backend (proxy). Así no dependes del puerto 8000 expuesto en el navegador.
 * - `npm run build` + preview o archivos estáticos: define `VITE_API_URL` (p. ej. http://localhost:8000) o se usa el host actual :8000.
 */
const PRODUCTION_API_URL = "https://ferragro-api.onrender.com";

function resolveApiBaseUrl() {
  const explicit = import.meta.env.VITE_API_URL;
  if (typeof explicit === "string" && explicit.trim()) {
    return explicit.trim().replace(/\/$/, "");
  }
  // En ejecución local (dev o preview en localhost), preferimos misma-origin
  // para usar el proxy de Vite hacia el backend local.
  if (typeof window !== "undefined") {
    const host = String(window.location.hostname || "").toLowerCase();
    if (host === "localhost" || host === "127.0.0.1" || host === "0.0.0.0") {
      return "";
    }
  }
  if (import.meta.env.DEV) {
    return "";
  }
  return PRODUCTION_API_URL;
}

function parseTimeoutMs(raw, fallback) {
  const n = Number(raw);
  return Number.isFinite(n) && n >= 5000 ? n : fallback;
}

/** Peticiones normales (listados, disponibilidad). En dev igual que prod: Render/local pueden tardar >10 s. */
export const API_TIMEOUT_MS = parseTimeoutMs(import.meta.env.VITE_API_TIMEOUT_MS, 60000);

/** Crear/reprogramar citas: el cold start de Render puede superar el timeout habitual. */
export const API_SLOW_TIMEOUT_MS = parseTimeoutMs(import.meta.env.VITE_API_SLOW_TIMEOUT_MS, 120000);

/** Login, registro y recuperar contraseña (cold start + bcrypt + BD en Render free). */
export const API_AUTH_TIMEOUT_MS = parseTimeoutMs(
  import.meta.env.VITE_API_AUTH_TIMEOUT_MS,
  API_SLOW_TIMEOUT_MS
);

let apiWakePromise = null;

/** True si axios abortó por tiempo de espera (la petición pudo completarse en el servidor). */
export function isApiTimeoutError(error) {
  return error?.code === "ECONNABORTED" || error?.code === "ETIMEDOUT";
}

/** Despierta el API (/health) antes de login u operaciones lentas (reintentos hasta ~90 s). */
export async function warmApi({ maxWaitMs = 90000 } = {}) {
  const base = resolveApiBaseUrl();
  const healthUrl = base ? `${base}/health` : "/health";
  if (apiWakePromise) {
    return apiWakePromise;
  }

  apiWakePromise = (async () => {
    const deadline = Date.now() + maxWaitMs;
    let attempt = 0;
    while (Date.now() < deadline) {
      attempt += 1;
      const controller = new AbortController();
      const timer = window.setTimeout(() => controller.abort(), 28000);
      try {
        const res = await fetch(healthUrl, {
          method: "GET",
          credentials: "omit",
          signal: controller.signal,
        });
        if (res.ok) {
          return;
        }
      } catch {
        /* Render free: primer intento suele fallar o abortar mientras despierta */
      } finally {
        window.clearTimeout(timer);
      }
      await new Promise((resolve) => {
        window.setTimeout(resolve, Math.min(4000, Math.max(1500, attempt * 800)));
      });
    }
  })().finally(() => {
    window.setTimeout(() => {
      apiWakePromise = null;
    }, 15000);
  });

  return apiWakePromise;
}

const api = axios.create({
  baseURL: resolveApiBaseUrl(),
  withCredentials: true,
  timeout: API_TIMEOUT_MS,
});

let refreshPromise = null;

function hasLocalSessionHint() {
  if (typeof window === "undefined") return true;
  return Boolean(sessionStorage.getItem("role") || sessionStorage.getItem("last_activity_at"));
}

/** Un solo refresh en vuelo (cookie rota el JTI; llamadas paralelas invalidan el access token). */
export function refreshAccessToken() {
  if (!hasLocalSessionHint()) {
    return Promise.reject(new Error("No hay sesión local para refrescar"));
  }
  if (!refreshPromise) {
    refreshPromise = api
      .post(`${API_PREFIX}/auth/refresh`)
      .then((refreshResponse) => {
        const refreshPayload = parseApiResponse(refreshResponse);
        if (!refreshPayload.success || !refreshPayload?.data?.access_token) {
          throw new Error(refreshPayload.message || "No se pudo refrescar la sesión");
        }
        setAccessToken(refreshPayload.data.access_token);
        return refreshPayload.data;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

export function clearAccessToken() {
  resetAccessToken();
  refreshPromise = null;
}

api.interceptors.request.use(async (config) => {
  const url = String(config?.url || "");
  const isAuthRoute =
    url.includes("/auth/login") ||
    url.includes("/auth/register") ||
    url.includes("/auth/forgot-password") ||
    url.includes("/auth/change-password");
  if (isAuthRoute && config.timeout == null) {
    config.timeout = API_AUTH_TIMEOUT_MS;
  }
  const isRefreshRequest = url.includes("/auth/refresh");
  if (refreshPromise && !isRefreshRequest) {
    try {
      await refreshPromise;
    } catch {
      /* el 401 del response interceptor gestionará la sesión */
    }
  }
  const token = getAccessToken();
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error?.response?.status;
    const originalRequest = error?.config || {};
    const requestUrl = String(originalRequest?.url || "");
    const isRefreshRequest = requestUrl.includes("/auth/refresh");
    const isLoginRequest = requestUrl.includes("/auth/login");
    const isLogoutRequest = requestUrl.includes("/auth/logout");

    if (
      !isRefreshRequest &&
      !isLoginRequest &&
      !isLogoutRequest &&
      status === 401 &&
      !originalRequest._retry &&
      hasLocalSessionHint()
    ) {
      originalRequest._retry = true;

      try {
        const refreshed = await refreshAccessToken();
        originalRequest.headers = originalRequest.headers || {};
        originalRequest.headers.Authorization = `Bearer ${refreshed.access_token}`;
        return api(originalRequest);
      } catch (refreshError) {
        if (typeof window !== "undefined") {
          window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
        }
        return Promise.reject(refreshError);
      }
    }

    if (status === 401 && typeof window !== "undefined" && hasLocalSessionHint() && !isLogoutRequest) {
      window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
    }
    return Promise.reject(error);
  }
);

/** Login con reintentos tras cold start de Render. */
export async function postLogin(email, password, { maxAttempts = 2 } = {}) {
  await warmApi();
  const trimmed = String(email || "").trim();
  let lastError = null;

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      const response = await api.post(
        `${API_PREFIX}/auth/login`,
        { email: trimmed, password },
        { timeout: API_AUTH_TIMEOUT_MS }
      );
      const payload = parseApiResponse(response);
      if (payload.success) {
        return { payload, emailUsed: trimmed };
      }
      throw new Error(payload.message || "Email o contraseña inválidos");
    } catch (error) {
      lastError = error;
      const canRetry = attempt < maxAttempts && isApiTimeoutError(error);
      if (!canRetry) {
        throw error;
      }
      await warmApi({ maxWaitMs: 60000 });
    }
  }

  throw lastError || new Error("No se pudo iniciar sesión");
}

export function parseApiResponse(response) {
  const payload = response?.data;
  if (!payload || typeof payload !== "object") {
    return { success: false, data: null, message: "Respuesta inválida del servidor" };
  }
  return payload;
}

/** True si el API rechazó la reserva por turno ocupado o capacidad del proveedor (HTTP 409). */
export function isAppointmentSlotConflict(error) {
  return Number(error?.response?.status) === 409;
}

export function parseApiError(error) {
  const status = error?.response?.status;
  const payload = error?.response?.data;
  if (payload?.message) {
    if (status === 422 && Array.isArray(payload?.data) && payload.data.length > 0) {
      const first = payload.data[0];
      const field = Array.isArray(first?.loc) ? first.loc.filter((part) => part !== "body").join(".") : "";
      const detail = String(first?.msg || "").trim();
      if (detail) {
        return field ? `${field}: ${detail}` : detail;
      }
    }
    return payload.message;
  }
  if (typeof payload?.detail === "string" && payload.detail.trim()) {
    const detail = payload.detail.trim();
    if (status === 404 && detail.toLowerCase() === "not found") {
      return import.meta.env.PROD
        ? "Recurso no encontrado en el API. Comprueba https://ferragro-api.onrender.com/health (build_id y render_git_commit). Si faltan rutas nuevas, haz Manual Deploy en Render; si /health está bien, redeploy en Vercel y Ctrl+F5."
        : "No se encontró el recurso solicitado. Comprueba que el backend local esté en marcha y actualizado.";
    }
    return detail;
  }
  if (Array.isArray(payload?.detail) && payload.detail.length > 0) {
    const first = payload.detail[0];
    if (typeof first === "string") return first;
    if (first?.msg) return String(first.msg);
  }
  if (isApiTimeoutError(error)) {
    const authPath = String(error?.config?.url || "");
    if (authPath.includes("/auth/login")) {
      return "El servidor tardó demasiado en despertar (Render). Espera unos segundos y pulsa Continuar de nuevo; no hace falta recargar la página.";
    }
    if (authPath.includes("/auth/forgot-password")) {
      return "El servidor tardó demasiado. Espera un momento y vuelve a solicitar la contraseña temporal.";
    }
    return "El servidor tardó demasiado en responder. Revisa «Ver mis citas» por si la operación sí se guardó antes de volver a intentar (el API en Render puede despertar al primer intento).";
  }
  if (error?.code === "ERR_NETWORK" || error?.message === "Network Error") {
    const dev = import.meta.env.DEV;
    return [
      "No se pudo conectar con el API.",
      dev
        ? "En modo desarrollo: arranca el backend en el puerto 8000 (por ejemplo `python main.py` en la carpeta backend) y recarga la página. Las peticiones a /api se reenvían desde Vite (puerto 2711) al 8000; no hace falta abrir el 8000 en el navegador."
        : "En producción: verifica VITE_API_URL=https://ferragro-api.onrender.com en Vercel y que el API esté activo.",
    ].join(" ");
  }
  if (error?.message && !error?.response) {
    return error.message;
  }
  return "No se pudo completar la operación";
}

/** True si el horario no coincide con un turno habilitado (HTTP 400). */
export function isAppointmentSlotWindowMismatch(error) {
  const msg = String(parseApiError(error) || "").toLowerCase();
  return msg.includes("no coinciden con un turno") || msg.includes("franja habilitada");
}

export function getRetryAfterSeconds(error) {
  const headers = error?.response?.headers || {};
  const retryAfterRaw = headers["retry-after"] ?? headers["Retry-After"];
  const retryAfterNumber = Number(retryAfterRaw);
  if (Number.isFinite(retryAfterNumber) && retryAfterNumber > 0) {
    return Math.max(1, Math.ceil(retryAfterNumber));
  }

  const resetRaw = headers["x-ratelimit-reset"] ?? headers["X-RateLimit-Reset"];
  const resetEpoch = Number(resetRaw);
  if (Number.isFinite(resetEpoch) && resetEpoch > 0) {
    const nowSec = Math.floor(Date.now() / 1000);
    const diff = resetEpoch - nowSec;
    if (diff > 0) return Math.max(1, diff);
  }

  const messageSource =
    String(error?.response?.data?.message || "") || String(error?.response?.data?.detail || "") || String(error?.message || "");
  const minutesMatch = messageSource.match(/(\d+)\s*minutos?/i);
  if (minutesMatch) {
    const minutes = Number(minutesMatch[1]);
    if (Number.isFinite(minutes) && minutes > 0) return minutes * 60;
  }
  const secondsMatch = messageSource.match(/(\d+)\s*segundos?/i);
  if (secondsMatch) {
    const seconds = Number(secondsMatch[1]);
    if (Number.isFinite(seconds) && seconds > 0) return seconds;
  }

  return 0;
}

export default api;
