import axios from "axios";

/** Versión del API en el servidor (routers montados en `/api` y `/api/v1`). */
export const API_PREFIX = (import.meta.env.VITE_API_PREFIX || "/api/v1").trim();

/**
 * - Con `npm run dev`: baseURL vacío → las peticiones van al mismo host/puerto del front (p. ej. :2711) y
 *   Vite reenvía `/api` y `/health` al backend (proxy). Así no dependes del puerto 8000 expuesto en el navegador.
 * - `npm run build` + preview o archivos estáticos: define `VITE_API_URL` (p. ej. http://localhost:8000) o se usa el host actual :8000.
 */
function resolveApiBaseUrl() {
  const explicit = import.meta.env.VITE_API_URL;
  if (typeof explicit === "string" && explicit.trim()) {
    return explicit.trim();
  }
  if (import.meta.env.DEV) {
    return "";
  }
  if (typeof window !== "undefined" && window.location?.hostname) {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return "http://localhost:8000";
}

const api = axios.create({
  baseURL: resolveApiBaseUrl(),
  withCredentials: true,
  timeout: 10000,
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
      !originalRequest._retry &&
      getAccessToken()
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

export function parseApiResponse(response) {
  const payload = response?.data;
  if (!payload || typeof payload !== "object") {
    return { success: false, data: null, message: "Respuesta inválida del servidor" };
  }
  return payload;
}

export function parseApiError(error) {
  const payload = error?.response?.data;
  if (payload?.message) {
    return payload.message;
  }
  if (typeof payload?.detail === "string" && payload.detail.trim()) {
    return payload.detail.trim();
  }
  if (Array.isArray(payload?.detail) && payload.detail.length > 0) {
    const first = payload.detail[0];
    if (typeof first === "string") return first;
    if (first?.msg) return String(first.msg);
  }
  if (error?.code === "ERR_NETWORK" || error?.message === "Network Error") {
    const dev = import.meta.env.DEV;
    return [
      "No se pudo conectar con el API.",
      dev
        ? "En modo desarrollo: arranca el backend en el puerto 8000 (por ejemplo `python main.py` en la carpeta backend) y recarga la página. Las peticiones a /api se reenvían desde Vite (puerto 2711) al 8000; no hace falta abrir el 8000 en el navegador."
        : "En producción: define la variable VITE_API_URL al construir el front (ej. http://tu-servidor:8000) y asegúrate de que el API esté accesible y CORS permita el origen de esta web.",
    ].join(" ");
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
