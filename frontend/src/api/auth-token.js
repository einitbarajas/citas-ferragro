/** Estado de token en memoria (sin axios) para no cargar el cliente HTTP en la ruta pública inicial. */
export const AUTH_EXPIRED_EVENT = "auth:expired";

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
