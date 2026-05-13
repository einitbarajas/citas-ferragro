import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import api, { AUTH_EXPIRED_EVENT, API_PREFIX, clearAccessToken, getAccessToken, setAccessToken } from "../api/client";

const AuthContext = createContext(null);
const INACTIVITY_TIMEOUT_MS = 15 * 60 * 1000;
const LAST_ACTIVITY_KEY = "last_activity_at";
const REDIRECT_TO_LOGIN_KEY = "redirect_to_login";
const AUTH_SESSION_CHANGED_EVENT = "auth:session-changed";

/** Solo bloquea el primer paint si hace falta `POST /auth/refresh` (actividad reciente). */
function needsRefreshBootstrap() {
  if (typeof window === "undefined") return false;
  const lastActivityAt = Number(sessionStorage.getItem(LAST_ACTIVITY_KEY) || 0);
  if (!lastActivityAt) return false;
  return Date.now() - lastActivityAt <= INACTIVITY_TIMEOUT_MS;
}

export function AuthProvider({ children }) {
  const inactivityTimerRef = useRef(null);
  const [isBootstrapping, setIsBootstrapping] = useState(needsRefreshBootstrap);

  const clearStoredSession = useCallback(() => {
    clearAccessToken();
    sessionStorage.removeItem("role");
    sessionStorage.removeItem("user_email");
    sessionStorage.removeItem(LAST_ACTIVITY_KEY);
  }, []);

  const [session, setSession] = useState(() => {
    const role = sessionStorage.getItem("role");
    const email = sessionStorage.getItem("user_email");
    return role ? { role, email: email || null } : null;
  });

  useEffect(() => {
    const bootstrap = async () => {
      const now = Date.now();
      const lastActivityAt = Number(sessionStorage.getItem(LAST_ACTIVITY_KEY) || 0);
      if (!lastActivityAt || now - lastActivityAt > INACTIVITY_TIMEOUT_MS) {
        clearStoredSession();
        setSession(null);
        setIsBootstrapping(false);
        return;
      }
      try {
        const refreshResponse = await api.post(`${API_PREFIX}/auth/refresh`);
        const payload = refreshResponse?.data;
        if (!payload?.success || !payload?.data?.access_token) {
          throw new Error("No se pudo recuperar sesión");
        }
        setAccessToken(payload.data.access_token);
        const role = payload?.data?.role || sessionStorage.getItem("role") || "";
        const email = sessionStorage.getItem("user_email");
        if (role) {
          sessionStorage.setItem("role", role);
        }
        sessionStorage.setItem(LAST_ACTIVITY_KEY, String(Date.now()));
        setSession({ role, email: email || null });
      } catch {
        clearStoredSession();
        setSession(null);
      } finally {
        setIsBootstrapping(false);
      }
    };
    bootstrap();
  }, [clearStoredSession]);

  const logout = useCallback(() => {
    api.post(`${API_PREFIX}/auth/logout`).catch(() => {
      // Si falla, limpiamos estado local de todas formas.
    });
    clearStoredSession();
    sessionStorage.setItem(REDIRECT_TO_LOGIN_KEY, "1");
    window.dispatchEvent(new Event(AUTH_SESSION_CHANGED_EVENT));
    setSession(null);
    if (typeof window !== "undefined") {
      window.history.replaceState({ ferragroAuth: "public" }, "", window.location.pathname);
    }
  }, [clearStoredSession]);

  const validateStoredSession = useCallback(async () => {
    const storedRole = sessionStorage.getItem("role");
    const hasRecentActivity = Boolean(sessionStorage.getItem(LAST_ACTIVITY_KEY));
    if (!storedRole && !hasRecentActivity && !getAccessToken()) {
      if (session) {
        clearStoredSession();
        setSession(null);
      }
      return;
    }
    if (!storedRole && !getAccessToken()) {
      clearStoredSession();
      setSession(null);
      return;
    }
    try {
      const refreshResponse = await api.post(`${API_PREFIX}/auth/refresh`);
      const payload = refreshResponse?.data;
      if (!payload?.success || !payload?.data?.access_token) {
        throw new Error(payload?.message || "No se pudo recuperar sesión");
      }
      setAccessToken(payload.data.access_token);
      const role = payload?.data?.role || storedRole || "";
      const email = sessionStorage.getItem("user_email");
      if (role) {
        sessionStorage.setItem("role", role);
      }
      sessionStorage.setItem(LAST_ACTIVITY_KEY, String(Date.now()));
      setSession({ role, email: email || null });
    } catch {
      clearStoredSession();
      sessionStorage.setItem(REDIRECT_TO_LOGIN_KEY, "1");
      window.dispatchEvent(new Event(AUTH_SESSION_CHANGED_EVENT));
      setSession(null);
    }
  }, [clearStoredSession, session]);

  const refreshActivity = useCallback(() => {
    sessionStorage.setItem(LAST_ACTIVITY_KEY, String(Date.now()));
    if (inactivityTimerRef.current) {
      window.clearTimeout(inactivityTimerRef.current);
    }
    inactivityTimerRef.current = window.setTimeout(() => {
      logout();
    }, INACTIVITY_TIMEOUT_MS);
  }, [logout]);

  useEffect(() => {
    if (!session) {
      if (inactivityTimerRef.current) {
        window.clearTimeout(inactivityTimerRef.current);
        inactivityTimerRef.current = null;
      }
      return undefined;
    }

    refreshActivity();
    const activityEvents = ["mousemove", "mousedown", "keydown", "scroll", "touchstart"];
    const onActivity = () => refreshActivity();
    const onAuthExpired = () => logout();

    activityEvents.forEach((eventName) => {
      window.addEventListener(eventName, onActivity, { passive: true });
    });
    window.addEventListener(AUTH_EXPIRED_EVENT, onAuthExpired);

    return () => {
      activityEvents.forEach((eventName) => {
        window.removeEventListener(eventName, onActivity);
      });
      window.removeEventListener(AUTH_EXPIRED_EVENT, onAuthExpired);
      if (inactivityTimerRef.current) {
        window.clearTimeout(inactivityTimerRef.current);
        inactivityTimerRef.current = null;
      }
    };
  }, [logout, refreshActivity, session]);

  useEffect(() => {
    if (isBootstrapping) return undefined;

    const onPageShow = (event) => {
      if (!event.persisted && !session && !sessionStorage.getItem("role")) return;
      void validateStoredSession();
    };
    const onVisibilityChange = () => {
      if (document.visibilityState !== "visible") return;
      if (!session && !sessionStorage.getItem("role")) return;
      void validateStoredSession();
    };

    window.addEventListener("pageshow", onPageShow);
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      window.removeEventListener("pageshow", onPageShow);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [isBootstrapping, session, validateStoredSession]);

  const value = useMemo(
    () => ({
      session,
      login: ({ token, role, email }) => {
        setAccessToken(token);
        sessionStorage.setItem("role", role);
        if (email) {
          sessionStorage.setItem("user_email", email);
        } else {
          sessionStorage.removeItem("user_email");
        }
        sessionStorage.setItem(LAST_ACTIVITY_KEY, String(Date.now()));
        window.dispatchEvent(new Event(AUTH_SESSION_CHANGED_EVENT));
        setSession({ role, email: email || null });
        if (typeof window !== "undefined") {
          window.history.replaceState({ ferragroAuth: "private" }, "", window.location.pathname);
        }
      },
      logout,
    }),
    [logout, session]
  );

  if (isBootstrapping) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4 text-slate-700">
        <section aria-live="polite" aria-busy="true" className="text-center">
          <h1 className="text-lg font-semibold">Cargando sesión</h1>
          <p className="mt-2 text-sm text-slate-600">Estamos validando tu acceso al portal.</p>
        </section>
      </main>
    );
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
