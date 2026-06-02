import { useEffect, useState } from "react";

import { PRODUCTION_API_URL } from "../api/client";
/** Fecha mínima en build_id (YYYY-MM-DD al inicio). Sincronizar con backend/app/main.py → API_BUILD_ID. */
const MIN_API_BUILD_DATE = "2026-05-21";
/** Opcional en Vercel: mismo valor que API_BUILD_ID en backend/app/main.py */
const EXPECTED_BUILD_ID = String(import.meta.env.VITE_EXPECTED_API_BUILD_ID || "").trim();
const LEGACY_OK_MARKERS = ["admin-bodega", "prod-sync", "prod-v1", "calendar-per-team", "deploy-main"];

function isApiBuildCurrent(buildId) {
  const bid = String(buildId || "").trim();
  if (!bid) return false;
  if (EXPECTED_BUILD_ID && bid === EXPECTED_BUILD_ID) return true;
  const dateMatch = /^(\d{4})-(\d{2})-(\d{2})/.exec(bid);
  if (dateMatch) {
    const buildDay = `${dateMatch[1]}-${dateMatch[2]}-${dateMatch[3]}`;
    if (buildDay >= MIN_API_BUILD_DATE) return true;
  }
  return LEGACY_OK_MARKERS.some((m) => bid.includes(m));
}

export default function ApiStaleBanner() {
  const [stale, setStale] = useState(false);
  const [buildId, setBuildId] = useState("");

  useEffect(() => {
    if (!import.meta.env.PROD) return;
    let cancelled = false;
    (async () => {
      try {
        const healthUrl =
          typeof window !== "undefined" && window.location.hostname.endsWith(".vercel.app")
            ? "/health"
            : `${PRODUCTION_API_URL}/health`;
        const res = await fetch(healthUrl, { credentials: "omit" });
        const json = await res.json();
        const bid = String(json?.data?.build_id || "");
        if (cancelled) return;
        setBuildId(bid);
        setStale(!isApiBuildCurrent(bid) && bid.length > 0);
      } catch {
        if (!cancelled) setStale(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (!stale) return null;

  return (
    <div
      className="mb-4 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-950"
      role="alert"
    >
      <p className="font-semibold">API en Render desactualizado ({buildId || "desconocido"})</p>
      <p className="mt-1">
        El portal es nuevo pero el servidor sigue en una versión de mayo. Un administrador debe hacer{" "}
        <strong>Manual Deploy → Deploy latest commit</strong> en{" "}
        <a
          href="https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0"
          target="_blank"
          rel="noopener noreferrer"
          className="font-medium underline"
        >
          ferragro-api (Render)
        </a>{" "}
        y esperar <strong>Live</strong>. Luego comprueba{" "}
        <a
          href={
            typeof window !== "undefined" && window.location.hostname.endsWith(".vercel.app")
              ? "/health"
              : `${PRODUCTION_API_URL}/health`
          }
          target="_blank"
          rel="noopener noreferrer"
          className="underline"
        >
          /health
        </a>{" "}
        (el <strong>build_id</strong> debe coincidir con el de <code>backend/app/main.py</code>).
      </p>
    </div>
  );
}
