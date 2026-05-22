import { useEffect, useState } from "react";

const PRODUCTION_API = "https://ferragro-api.onrender.com";
/** Mínimo build_id que el front actual necesita (actualizar al desplegar API). */
const MIN_API_BUILD_PREFIX = "2026-05-21";

export default function ApiStaleBanner() {
  const [stale, setStale] = useState(false);
  const [buildId, setBuildId] = useState("");

  useEffect(() => {
    if (!import.meta.env.PROD) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${PRODUCTION_API}/health`, { credentials: "omit" });
        const json = await res.json();
        const bid = String(json?.data?.build_id || "");
        if (cancelled) return;
        setBuildId(bid);
        const ok =
          bid.startsWith(MIN_API_BUILD_PREFIX) ||
          bid.includes("admin-bodega") ||
          bid.includes("prod-sync") ||
          bid.includes("calendar-per-team");
        setStale(!ok && bid.length > 0);
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
          href={`${PRODUCTION_API}/health`}
          target="_blank"
          rel="noopener noreferrer"
          className="underline"
        >
          /health
        </a>{" "}
        (debe mostrar un build_id de 2026-05-22).
      </p>
    </div>
  );
}
