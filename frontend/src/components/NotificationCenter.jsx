import { useCallback, useEffect, useRef, useState } from "react";
import api, { API_PREFIX, parseApiError, parseApiResponse } from "../api/client";

const POLL_MS = 60_000;

function formatWhen(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("es-CO", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function NotificationCenter({ onNavigate }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [unreadTotal, setUnreadTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const panelRef = useRef(null);

  const loadNotifications = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get(`${API_PREFIX}/notifications`, {
        params: { page: 1, page_size: 20 },
      });
      const payload = parseApiResponse(response);
      if (!payload.success) {
        setError(payload.message || "No se pudieron cargar las notificaciones.");
        return;
      }
      const data = payload.data || {};
      setItems(Array.isArray(data.items) ? data.items : []);
      setUnreadTotal(Number(data.unread_total || 0));
      setError("");
    } catch (err) {
      setError(parseApiError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadNotifications();
    const timer = window.setInterval(loadNotifications, POLL_MS);
    return () => window.clearInterval(timer);
  }, [loadNotifications]);

  useEffect(() => {
    if (!open) return undefined;
    const onPointerDown = (event) => {
      if (panelRef.current && !panelRef.current.contains(event.target)) {
        setOpen(false);
      }
    };
    const onKeyDown = (event) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const markRead = async (notificationId) => {
    try {
      await api.patch(`${API_PREFIX}/notifications/${notificationId}/read`);
      setItems((prev) =>
        prev.map((item) =>
          item.id === notificationId ? { ...item, read: true, read_at: new Date().toISOString() } : item
        )
      );
      setUnreadTotal((prev) => Math.max(0, prev - 1));
    } catch {
      /* ignore */
    }
  };

  const markAllRead = async () => {
    try {
      await api.patch(`${API_PREFIX}/notifications/read-all`);
      setItems((prev) => prev.map((item) => ({ ...item, read: true })));
      setUnreadTotal(0);
    } catch {
      /* ignore */
    }
  };

  const onItemClick = async (item) => {
    if (!item.read) await markRead(item.id);
    setOpen(false);
    if (typeof onNavigate === "function") {
      onNavigate(item);
    }
  };

  const badge = unreadTotal > 99 ? "99+" : String(unreadTotal);

  return (
    <div ref={panelRef} className="relative" data-tour="notification-center">
      <button
        type="button"
        data-tour="notification-trigger"
        onClick={() => {
          setOpen((prev) => !prev);
          if (!open) loadNotifications();
        }}
        className="relative inline-flex min-h-10 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-700 transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#35783C]/40"
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label={unreadTotal > 0 ? `Notificaciones, ${unreadTotal} sin leer` : "Notificaciones"}
      >
        <span aria-hidden="true" className="text-base leading-none">
          🔔
        </span>
        <span className="hidden sm:inline">Notificaciones</span>
        {unreadTotal > 0 ? (
          <span className="absolute -right-1 -top-1 inline-flex min-h-5 min-w-5 items-center justify-center rounded-full bg-amber-500 px-1 text-[10px] font-bold text-white">
            {badge}
          </span>
        ) : null}
      </button>

      {open ? (
        <div
          role="dialog"
          aria-label="Centro de notificaciones"
          className="absolute right-0 z-50 mt-2 w-[min(22rem,calc(100vw-2rem))] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl"
        >
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <p className="text-sm font-semibold text-slate-900">Notificaciones</p>
            <button
              type="button"
              onClick={markAllRead}
              disabled={unreadTotal === 0}
              className="text-xs font-medium text-emerald-700 transition hover:text-emerald-900 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Marcar todas leídas
            </button>
          </div>

          <div className="max-h-80 overflow-y-auto">
            {loading && items.length === 0 ? (
              <p className="px-4 py-6 text-center text-sm text-slate-500">Cargando…</p>
            ) : null}
            {error ? <p className="px-4 py-3 text-sm text-red-600">{error}</p> : null}
            {!loading && !error && items.length === 0 ? (
              <p className="px-4 py-6 text-center text-sm text-slate-500">No tienes notificaciones.</p>
            ) : null}
            {items.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => onItemClick(item)}
                className={`block w-full border-b border-slate-100 px-4 py-3 text-left transition hover:bg-slate-50 ${
                  item.read ? "bg-white" : "bg-amber-50/60"
                }`}
              >
                <p className="text-sm font-semibold text-slate-900">{item.title}</p>
                <p className="mt-1 text-xs leading-relaxed text-slate-600">{item.message}</p>
                <p className="mt-2 text-[10px] uppercase tracking-wide text-slate-500">{formatWhen(item.created_at)}</p>
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
