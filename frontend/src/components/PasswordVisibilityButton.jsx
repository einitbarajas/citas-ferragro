export default function PasswordVisibilityButton({ visible, onToggle, label = "contraseña" }) {
  const showLabel = label ? ` ${label}` : "";

  return (
    <button
      type="button"
      onPointerDown={(e) => e.preventDefault()}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        onToggle();
      }}
      className="absolute inset-y-0 right-0 z-10 flex w-10 cursor-pointer touch-manipulation items-center justify-center rounded-r-lg text-slate-600 transition hover:bg-slate-50/80 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#35783C]/40 dark:hover:bg-slate-800/80 dark:text-slate-200"
      aria-label={visible ? `Ocultar${showLabel}` : `Mostrar${showLabel}`}
      aria-pressed={visible}
    >
      {visible ? (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M3 3l18 18" />
          <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8" />
          <path d="M9.9 5.1A10.9 10.9 0 0 1 12 5c5.1 0 9.3 3.2 10.8 7-1 2.4-3 4.4-5.6 5.7" />
          <path d="M6.2 6.2C3.7 7.6 1.9 9.7 1.2 12c1.5 3.8 5.7 7 10.8 7 1.1 0 2.2-.2 3.2-.5" />
        </svg>
      ) : (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7z" />
          <circle cx="12" cy="12" r="3" />
        </svg>
      )}
    </button>
  );
}
