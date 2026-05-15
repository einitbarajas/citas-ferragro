import { useTheme } from "../context/ThemeContext";

const baseBtn =
  "inline-flex items-center justify-center gap-2 rounded-full border border-slate-300 bg-white/95 font-semibold text-slate-700 shadow-lg backdrop-blur transition-colors duration-300 ease-out hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/40 dark:border-slate-700 dark:bg-slate-900/95 dark:text-slate-100 dark:hover:bg-slate-800";

/**
 * @param {"fixed" | "inline"} variant
 * - fixed: esquina (arriba en móvil, abajo en escritorio)
 * - inline: junto a otros controles del encabezado (sin position fixed)
 */
export default function ThemeToggle({ variant = "fixed", className = "" }) {
  const { isDark, toggleTheme } = useTheme();

  const placementClass =
    variant === "inline"
      ? "min-h-10 min-w-10 shrink-0 px-2.5 py-2 text-sm shadow-sm"
      : "fixed right-4 z-[50] min-h-11 min-w-11 px-3 py-2 text-sm max-lg:top-[max(0.75rem,env(safe-area-inset-top))] lg:bottom-4 lg:top-auto lg:z-[45] lg:px-4";

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className={`${baseBtn} ${placementClass} ${className}`.trim()}
      aria-label={isDark ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
      title={isDark ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
    >
      <span aria-hidden="true">{isDark ? "☀" : "🌙"}</span>
      <span className={variant === "inline" ? "sr-only" : "hidden sm:inline"}>
        {isDark ? "Claro" : "Oscuro"}
      </span>
    </button>
  );
}
