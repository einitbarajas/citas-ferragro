import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useState } from "react";
import { flushSync } from "react-dom";

const THEME_STORAGE_KEY = "ferragro_theme";
const AUTH_SESSION_CHANGED_EVENT = "auth:session-changed";
const ThemeContext = createContext(null);

function getThemeStorageKey() {
  if (typeof window === "undefined") return THEME_STORAGE_KEY;
  const rawEmail = window.sessionStorage.getItem("user_email") || "";
  const email = rawEmail.trim().toLowerCase();
  if (!email) return THEME_STORAGE_KEY;
  return `${THEME_STORAGE_KEY}:${email}`;
}

function getInitialTheme() {
  if (typeof window === "undefined") return "light";
  const stored = window.localStorage.getItem(getThemeStorageKey());
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia?.("(prefers-color-scheme: dark)")?.matches ? "dark" : "light";
}

export function ThemeProvider({ children }) {
  const [storageKey, setStorageKey] = useState(getThemeStorageKey);
  const [theme, setTheme] = useState(getInitialTheme);

  useLayoutEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", theme === "dark");
    root.style.colorScheme = theme;
    window.localStorage.setItem(storageKey, theme);
  }, [storageKey, theme]);

  useEffect(() => {
    const syncThemeFromSession = () => {
      const nextKey = getThemeStorageKey();
      setStorageKey((prev) => (prev === nextKey ? prev : nextKey));
      const stored = window.localStorage.getItem(nextKey);
      if (stored === "light" || stored === "dark") {
        setTheme(stored);
      }
    };
    window.addEventListener(AUTH_SESSION_CHANGED_EVENT, syncThemeFromSession);
    return () => window.removeEventListener(AUTH_SESSION_CHANGED_EVENT, syncThemeFromSession);
  }, []);

  const toggleTheme = useCallback(() => {
    const flip = (prev) => (prev === "dark" ? "light" : "dark");
    if (
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      setTheme(flip);
      return;
    }
    const startVT = typeof document !== "undefined" ? document.startViewTransition?.bind(document) : null;
    if (!startVT) {
      setTheme(flip);
      return;
    }
    startVT(() => {
      flushSync(() => {
        setTheme(flip);
      });
    });
  }, []);

  const value = useMemo(
    () => ({
      theme,
      isDark: theme === "dark",
      setTheme,
      toggleTheme,
    }),
    [theme, toggleTheme]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme debe usarse dentro de ThemeProvider");
  }
  return context;
}

