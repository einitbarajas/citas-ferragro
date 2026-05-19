import axios from "axios";

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
  if (import.meta.env.DEV) {
    return "";
  }
  return PRODUCTION_API_URL;
}

/** Tras despertar el API, el login suele responder en pocos segundos. */
const API_TIMEOUT_MS = import.meta.env.PROD ? 35000 : 10000;

let apiWakePromise = null;

/** Despierta el API en Render (plan Free) antes del login. */
export function warmApi() {
  const base = resolveApiBaseUrl();
  if (!base || import.meta.env.DEV) {
    return Promise.resolve();
  }
  if (!apiWakePromise) {
    apiWakePromise = fetch(`${base}/health`, { method: "GET", credentials: "omit" })
      .catch(() => {})
      .finally(() => {
        setTimeout(() => {
          apiWakePromise = null;
        }, 20000);
      });
  }
  return apiWakePromise;
}

const api = axios.create({
  baseURL: resolveApiBaseUrl(),
  withCredentials: true,
  timeout: API_TIMEOUT_MS,
});

export const AUTH_EXPIRED_EVENT = "auth:expired";
const UNAUTHORIZED_STATUSES = new Set([401, 403]);
let refreshPromise = null;
let accessToken = "";

export function setAccessToken(token) {
  accessToken = String(token || "").trim();
}

export function clearAccessToken() {
  accessToken = "";
}

export function getAccessToken() {
  return accessToken;
}

api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
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
      UNAUTHORIZED_STATUSES.has(status) &&
      !originalRequest._retry
    ) {
      originalRequest._retry = true;
      if (!refreshPromise) {
        refreshPromise = api
          .post(`${API_PREFIX}/auth/refresh`)
          .then((refreshResponse) => {
            const refreshPayload = parseApiResponse(refreshResponse);
            if (!refreshPayload.success || !refreshPayload?.data?.access_token) {
              throw new Error(refreshPayload.message || "No se pudo refrescar la sesión");
            }
            setAccessToken(refreshPayload.data.access_token);
            return refreshPayload.data.access_token;
          })
          .finally(() => {
            refreshPromise = null;
          });
      }

      try {
        const newAccessToken = await refreshPromise;
        originalRequest.headers = originalRequest.headers || {};
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        return api(originalRequest);
      } catch (refreshError) {
        if (typeof window !== "undefined") {
          window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
        }
        return Promise.reject(refreshError);
      }
    }

    if (status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
    }
    return Promise.reject(error);
  }
);

/** Login (un solo intento; el API ya resuelve correo sin distinguir mayúsculas). */
export async function postLogin(email, password) {
  await warmApi();
  const trimmed = String(email || "").trim();
  const response = await api.post(`${API_PREFIX}/auth/login`, { email: trimmed, password });
  const payload = parseApiResponse(response);
  if (payload.success) {
    return { payload, emailUsed: trimmed };
  }
  throw new Error(payload.message || "Email o contraseña inválidos");
}

export function parseApiResponse(response) {
  const payload = response?.data;
  if (!payload || typeof payload !== "object") {
    return { success: false, data: null, message: "Respuesta inválida del servidor" };
  }
  return payload;
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
      return "No se encontró el recurso solicitado. Si acabas de actualizar el sistema, reinicia el backend.";
    }
    return detail;
  }
  if (Array.isArray(payload?.detail) && payload.detail.length > 0) {
    const first = payload.detail[0];
    if (typeof first === "string") return first;
    if (first?.msg) return String(first.msg);
  }
  if (error?.code === "ECONNABORTED" || error?.code === "ETIMEDOUT") {
    return "El servidor tardó demasiado en responder. Espera unos segundos e intenta de nuevo (el API en Render puede despertar al primer intento).";
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
