import { useEffect, useState } from "react";

const PRODUCTION_API = "https://ferragro-api.onrender.com";
/** Prefijos de build_id que indican API al día (no confundir con la fecha del deploy). */
const OK_API_BUILD_PREFIXES = ["2026-05-21", "2026-05-22", "2026-05-25"];
const OK_API_BUILD_MARKERS = ["admin-bodega", "prod-sync", "prod-v1", "calendar-per-team"];

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
        const git = String(json?.data?.render_git_commit || "");
        const ok =
          OK_API_BUILD_PREFIXES.some((p) => bid.startsWith(p)) ||
          OK_API_BUILD_MARKERS.some((m) => bid.includes(m)) ||
          (git.length >= 7 && bid.includes("prod"));
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
        (debe incluir <strong>prod-sync</strong> o un <strong>render_git_commit</strong> reciente).
      </p>
    </div>
  );
}
