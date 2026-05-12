import { useEffect, useMemo, useState } from "react";

function setCookie(name, value, { maxAgeSeconds = 60 * 60 * 24 * 365, path = "/" } = {}) {
  document.cookie = `${encodeURIComponent(name)}=${encodeURIComponent(value)}; Max-Age=${maxAgeSeconds}; Path=${path}; SameSite=Lax`;
}

function getCookie(name) {
  const target = `${encodeURIComponent(name)}=`;
  const parts = document.cookie.split(";").map((p) => p.trim());
  const found = parts.find((p) => p.startsWith(target));
  if (!found) return null;
  return decodeURIComponent(found.slice(target.length));
}

export default function CookieBanner() {
  const initiallyAccepted = useMemo(() => {
    try {
      return localStorage.getItem("cookie_consent") === "accepted";
    } catch {
      return false;
    }
  }, []);

  const [accepted, setAccepted] = useState(initiallyAccepted);

  useEffect(() => {
    if (accepted) return;
    const cookieAccepted = getCookie("cookie_consent") === "accepted";
    if (cookieAccepted) {
      try {
        localStorage.setItem("cookie_consent", "accepted");
      } catch {
        // ignore
      }
      setAccepted(true);
    }
  }, [accepted]);

  const accept = () => {
    try {
      localStorage.setItem("cookie_consent", "accepted");
    } catch {
      // ignore
    }
    setCookie("cookie_consent", "accepted");
    setAccepted(true);
  };

  if (accepted) return null;

  return (
    <div
      role="region"
      aria-label="Aviso de cookies"
      className="fixed inset-x-0 bottom-0 z-50 border-t border-[#D7D8D8] bg-white/95 px-4 py-4 shadow-2xl backdrop-blur"
    >
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="text-sm text-slate-700">
          <p className="font-medium text-[#121212]">Cookies</p>
          <p className="mt-0.5">
            Usamos cookies para recordar tu sesión y mejorar la experiencia. Al continuar aceptas su uso.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={accept}
            className="rounded-lg bg-[#35783C] px-4 py-2 text-sm font-medium text-white shadow-sm shadow-emerald-200 transition hover:bg-[#2d6532] focus:outline-none focus:ring-2 focus:ring-[#35783C]/30"
          >
            Aceptar
          </button>
        </div>
      </div>
    </div>
  );
}

