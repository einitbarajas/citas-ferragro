import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

const SPOTLIGHT_CLASS = "guided-tour-spotlight";
const MASK_PAD = 10;

function defaultTipForStep(step, stepIndex) {
  if (step.tip) return step.tip;
  if (stepIndex === 0) {
    if (Array.isArray(step.bullets) && step.bullets.length > 0) return null;
    return "Esta guía solo explica la pantalla: no guarda cambios ni envía nada por sí sola.";
  }
  return null;
}

function defaultAhoraLine(step) {
  if (step.ahora) return step.ahora;
  const t = String(step.title || "");
  if (t.startsWith("Contenido:")) {
    return "Mira el panel central (zona grande): ahí trabajas con formularios y listas.";
  }
  if (t.startsWith("Ítem:")) {
    return "Mira el menú de la izquierda. En el móvil, ábrelo con el botón \"Menú\" arriba; el ítem relacionado puede aparecer resaltado en verde.";
  }
  if (t.includes("Pie del menú") || t.includes("Cerrar sesión") || t.includes("tu perfil")) {
    return "Mira la parte de abajo del menú lateral (o del menú desplegable en el móvil).";
  }
  if (t.includes("Marca del panel") || t.includes("Área de navegación")) {
    return "Mira la columna del menú: arriba está la marca y debajo la lista de secciones.";
  }
  return null;
}

function resolveTargetElement(selector) {
  if (!selector || typeof selector !== "string") return null;
  let el = document.querySelector(selector);
  if (el) return el;
  if (selector.includes("section-citas") || selector.includes("section-proveedor")) {
    const main = document.querySelector('[data-tour="main-workspace"]');
    if (main) return main;
  }
  return null;
}

function clamp(n, min, max) {
  return Math.min(Math.max(n, min), max);
}

/**
 * Guía tipo “coach”: oscurece el resto con una máscara con agujero alrededor del objetivo
 * y muestra un recuadro pequeño con el texto (no tapa toda la pantalla).
 */
function SpotMask({ rect, onDimClick }) {
  const vw = typeof window !== "undefined" ? window.innerWidth : 0;
  const vh = typeof window !== "undefined" ? window.innerHeight : 0;
  const onSeg = (e) => {
    e.stopPropagation();
    onDimClick?.();
  };
  if (!rect || vw <= 0 || vh <= 0) {
    return (
      <button
        type="button"
        className="fixed inset-0 z-[100050] cursor-default border-0 bg-slate-900/40 p-0 dark:bg-slate-950/55"
        aria-label="Cerrar guía"
        onClick={onSeg}
      />
    );
  }
  const t = clamp(rect.top - MASK_PAD, 0, vh);
  const l = clamp(rect.left - MASK_PAD, 0, vw);
  const r = clamp(rect.right + MASK_PAD, 0, vw);
  const b = clamp(rect.bottom + MASK_PAD, 0, vh);
  const dim =
    "fixed z-[100050] cursor-default border-0 bg-slate-900/40 p-0 dark:bg-slate-950/55";
  return (
    <>
      <button type="button" className={dim} style={{ top: 0, left: 0, right: 0, height: t }} aria-label="Cerrar guía" onClick={onSeg} />
      <button type="button" className={dim} style={{ top: t, left: 0, width: l, height: Math.max(0, b - t) }} aria-label="Cerrar guía" onClick={onSeg} />
      <button type="button" className={dim} style={{ top: t, left: r, right: 0, height: Math.max(0, b - t) }} aria-label="Cerrar guía" onClick={onSeg} />
      <button type="button" className={dim} style={{ top: b, left: 0, right: 0, bottom: 0 }} aria-label="Cerrar guía" onClick={onSeg} />
    </>
  );
}

export default function GuidedTourDialog({
  open,
  steps,
  stepIndex,
  onStepIndexChange,
  onClose,
  label = "Guía",
  /**
   * Opcional. Cuando cambia (p. ej. pestaña o menú del panel), se vuelve a colocar el resaltado
   * después de que el padre haya actualizado el DOM (evita perder la clase al avanzar paso).
   */
  spotlightLayoutKey = "",
}) {
  const cardRef = useRef(null);
  const spotlightElRef = useRef(null);

  const [targetRect, setTargetRect] = useState(null);
  const [bubbleStyle, setBubbleStyle] = useState({ mode: "center" });

  const safeIndex = Math.min(Math.max(0, stepIndex), Math.max(0, (steps?.length || 1) - 1));
  const n = Array.isArray(steps) ? steps.length : 0;
  const step = n > 0 ? steps[safeIndex] : null;

  const isFirst = safeIndex <= 0;
  const isLast = n > 0 && safeIndex >= n - 1;
  const progressPct = n > 0 ? Math.round(((safeIndex + 1) / n) * 100) : 0;

  const tip = step ? defaultTipForStep(step, safeIndex) : null;
  const ahora = step ? defaultAhoraLine(step) : null;

  const updateLayout = useCallback(() => {
    const el = spotlightElRef.current;
    if (!el || !open) {
      setTargetRect(null);
      setBubbleStyle({ mode: "center" });
      return;
    }
    const rect = el.getBoundingClientRect();
    if (rect.width < 2 && rect.height < 2) {
      setTargetRect(null);
      setBubbleStyle({ mode: "center" });
      return;
    }
    setTargetRect({
      top: rect.top,
      left: rect.left,
      right: rect.right,
      bottom: rect.bottom,
      width: rect.width,
      height: rect.height,
    });

    const margin = 12;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const isNarrow = vw < 640;
    const bubbleW = Math.min(380, vw - margin * 2);
    const bubbleHGuess = 280;

    if (isNarrow) {
      setBubbleStyle({
        mode: "bottom",
        left: margin,
        right: margin,
        bottom: margin + (window.visualViewport?.offsetTop ? 0 : 0),
        maxWidth: bubbleW,
      });
      return;
    }

    const spaceRight = vw - rect.right - margin;
    const spaceLeft = rect.left - margin;
    const preferRight = spaceRight >= bubbleW - 40 || spaceRight >= spaceLeft;

    let left;
    let top = rect.top + rect.height / 2 - bubbleHGuess / 2;
    top = clamp(top, margin, vh - bubbleHGuess - margin);

    if (preferRight && spaceRight > 160) {
      left = rect.right + margin;
      left = clamp(left, margin, vw - bubbleW - margin);
      setBubbleStyle({ mode: "side", left, top, maxWidth: bubbleW });
    } else if (spaceLeft > 160) {
      left = rect.left - margin - bubbleW;
      left = clamp(left, margin, vw - bubbleW - margin);
      setBubbleStyle({ mode: "side", left, top, maxWidth: bubbleW });
    } else {
      let topBelow = rect.bottom + margin;
      if (topBelow + bubbleHGuess > vh - margin) {
        topBelow = rect.top - margin - bubbleHGuess;
      }
      topBelow = clamp(topBelow, margin, vh - bubbleHGuess - margin);
      setBubbleStyle({
        mode: "below",
        left: clamp(rect.left, margin, vw - bubbleW - margin),
        top: topBelow,
        maxWidth: bubbleW,
      });
    }
  }, [open]);

  useEffect(() => {
    if (!open || !step) {
      if (spotlightElRef.current) {
        spotlightElRef.current.classList.remove(SPOTLIGHT_CLASS);
        spotlightElRef.current = null;
      }
      setTargetRect(null);
      setBubbleStyle({ mode: "center" });
      return;
    }

    let cancelled = false;
    let timer = 0;
    let rafOuter = 0;
    let rafInner = 0;
    let mainEl = null;

    const onScrollOrResize = () => updateLayout();

    const detachListeners = () => {
      window.removeEventListener("resize", onScrollOrResize);
      mainEl?.removeEventListener("scroll", onScrollOrResize, true);
      window.visualViewport?.removeEventListener("resize", onScrollOrResize);
      window.visualViewport?.removeEventListener("scroll", onScrollOrResize);
      mainEl = null;
    };

    const applySpotlight = () => {
      if (cancelled) return;

      detachListeners();

      const prev = spotlightElRef.current;
      if (prev) prev.classList.remove(SPOTLIGHT_CLASS);

      const el = resolveTargetElement(step.targetSelector);
      spotlightElRef.current = el;
      if (el) {
        el.classList.add(SPOTLIGHT_CLASS);
        el.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
      }

      cancelAnimationFrame(rafOuter);
      cancelAnimationFrame(rafInner);
      rafOuter = requestAnimationFrame(() => {
        rafInner = requestAnimationFrame(() => updateLayout());
      });

      window.addEventListener("resize", onScrollOrResize);
      mainEl = document.querySelector('[data-tour="main-workspace"]');
      mainEl?.addEventListener("scroll", onScrollOrResize, true);
      window.visualViewport?.addEventListener("resize", onScrollOrResize);
      window.visualViewport?.addEventListener("scroll", onScrollOrResize);
    };

    /** Tras el commit: primero el padre (Dashboard) puede hacer flushSync del tab; luego aplicamos la clase al nodo ya estable. */
    timer = window.setTimeout(applySpotlight, 0);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      cancelAnimationFrame(rafOuter);
      cancelAnimationFrame(rafInner);
      detachListeners();
      const cur = spotlightElRef.current;
      if (cur) cur.classList.remove(SPOTLIGHT_CLASS);
      spotlightElRef.current = null;
    };
  }, [open, safeIndex, step?.targetSelector, spotlightLayoutKey, updateLayout]);

  const onKeyDown = useCallback(
    (e) => {
      if (!open || !n) return;
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key === "ArrowRight" || e.key === "Enter") {
        e.preventDefault();
        if (isLast) onClose();
        else onStepIndexChange(safeIndex + 1);
        return;
      }
      if (e.key === "ArrowLeft" && !isFirst) {
        e.preventDefault();
        onStepIndexChange(safeIndex - 1);
      }
    },
    [open, n, isLast, isFirst, safeIndex, onClose, onStepIndexChange]
  );

  useEffect(() => {
    if (!open) return;
    document.addEventListener("keydown", onKeyDown, true);
    return () => document.removeEventListener("keydown", onKeyDown, true);
  }, [open, onKeyDown]);

  useEffect(() => {
    if (!open || !cardRef.current) return;
    const t = window.setTimeout(() => {
      cardRef.current?.focus?.();
    }, 80);
    return () => window.clearTimeout(t);
  }, [open, safeIndex]);

  if (!open || !step || n === 0) return null;

  const bullets = Array.isArray(step.bullets) ? step.bullets.filter(Boolean) : [];

  /** Misma tarjeta en todos los modos: altura máxima + scroll interno si el texto no cabe. */
  const bubblePositionClass =
    bubbleStyle.mode === "bottom"
      ? "fixed z-[100060] max-h-[min(52vh,420px)] min-h-0 w-auto overflow-y-auto overscroll-behavior-contain"
      : bubbleStyle.mode === "center"
        ? "fixed left-1/2 top-1/2 z-[100060] max-h-[min(85vh,520px)] min-h-0 w-[min(92vw,400px)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto overscroll-behavior-contain"
        : "fixed z-[100060] max-h-[min(80vh,480px)] min-h-0 overflow-y-auto overscroll-behavior-contain";

  const bubblePositionStyle =
    bubbleStyle.mode === "bottom"
      ? {
          left: bubbleStyle.left,
          right: bubbleStyle.right,
          bottom: bubbleStyle.bottom ?? 16,
          maxWidth: bubbleStyle.maxWidth,
        }
      : bubbleStyle.mode === "center"
        ? {}
        : {
            left: bubbleStyle.left,
            top: bubbleStyle.top,
            maxWidth: bubbleStyle.maxWidth,
          };

  const ui = (
    <>
      <SpotMask rect={targetRect} onDimClick={onClose} />
      <div
        ref={cardRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby="guided-tour-title"
        aria-describedby="guided-tour-body"
        style={bubblePositionStyle}
        className={`${bubblePositionClass} rounded-2xl border border-slate-200 bg-white shadow-2xl outline-none dark:border-slate-600 dark:bg-slate-900`}
      >
        <div className="p-4 sm:p-5">
          <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
            <div className="flex min-w-0 flex-1 items-center gap-2.5">
              <div
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-100 text-sm font-bold text-emerald-900 dark:bg-emerald-900/50 dark:text-emerald-100"
                aria-hidden="true"
              >
                {safeIndex + 1}
              </div>
              <div className="min-w-0">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-emerald-700 dark:text-emerald-400">
                  {label}
                </p>
                <p className="text-[11px] text-slate-500 dark:text-slate-400">
                  Paso {safeIndex + 1} de {n} · {progressPct}%
                </p>
              </div>
            </div>
            <button
              type="button"
              className="inline-flex h-9 min-w-9 shrink-0 items-center justify-center rounded-lg border border-slate-200 text-base leading-none text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
              aria-label="Cerrar guía"
              onClick={onClose}
            >
              ×
            </button>
          </div>

          <div className="mb-3 h-1.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800" aria-hidden="true">
            <div
              className="h-full rounded-full bg-[#35783C] transition-[width] duration-300 ease-out"
              style={{ width: `${progressPct}%` }}
            />
          </div>

          <h2 id="guided-tour-title" className="text-base font-bold leading-snug text-slate-900 dark:text-white sm:text-lg">
            {step.title}
          </h2>
          {step.subtitle ? (
            <p className="mt-0.5 text-xs font-medium text-emerald-800 dark:text-emerald-300">{step.subtitle}</p>
          ) : null}

          <div id="guided-tour-body" className="mt-3 space-y-3">
            {step.description ? (
              <p className="text-xs leading-relaxed text-slate-700 dark:text-slate-200 sm:text-sm">{step.description}</p>
            ) : null}
            {bullets.length > 0 ? (
              <ul className="list-none space-y-2 text-xs leading-relaxed text-slate-700 dark:text-slate-200 sm:text-sm">
                {bullets.map((line, i) => (
                  <li key={i} className="flex gap-2">
                    <span
                      className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-[9px] font-bold text-white"
                      aria-hidden="true"
                    >
                      ✓
                    </span>
                    <span>{line}</span>
                  </li>
                ))}
              </ul>
            ) : null}

            {ahora ? (
              <div className="rounded-lg border border-emerald-200 bg-emerald-50/90 px-2.5 py-2 dark:border-emerald-800 dark:bg-emerald-950/40">
                <p className="text-[10px] font-bold uppercase tracking-wide text-emerald-800 dark:text-emerald-300">
                  Qué mirar ahora
                </p>
                <p className="mt-0.5 text-xs text-emerald-950 dark:text-emerald-100">{ahora}</p>
              </div>
            ) : null}

            {tip ? (
              <div className="rounded-lg border border-amber-200 bg-amber-50/95 px-2.5 py-2 dark:border-amber-900/60 dark:bg-amber-950/30">
                <p className="text-[10px] font-bold uppercase tracking-wide text-amber-900 dark:text-amber-200">
                  Consejo
                </p>
                <p className="mt-0.5 text-xs text-amber-950 dark:text-amber-50">{tip}</p>
              </div>
            ) : null}
          </div>

          <p className="mt-3 text-center text-[10px] text-slate-500 dark:text-slate-400">
            Flecha derecha o Enter = siguiente · Izquierda = anterior · Esc = cerrar
          </p>

          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-3 dark:border-slate-700">
            <button
              type="button"
              disabled={isFirst}
              onClick={() => onStepIndexChange(safeIndex - 1)}
              className="min-h-10 min-w-[6.5rem] rounded-lg border border-slate-300 bg-white px-3 text-xs font-semibold text-slate-800 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-45 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100 dark:hover:bg-slate-700 sm:text-sm"
            >
              ← Anterior
            </button>
            <div className="flex flex-1 justify-end gap-2 sm:flex-initial">
              {isLast ? (
                <button
                  type="button"
                  onClick={onClose}
                  className="min-h-10 rounded-lg bg-[#35783C] px-4 text-xs font-semibold text-white shadow-sm transition hover:bg-[#2d6532] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#35783C]/40 sm:text-sm"
                >
                  Listo
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => onStepIndexChange(safeIndex + 1)}
                  className="min-h-10 rounded-lg bg-[#35783C] px-4 text-xs font-semibold text-white shadow-sm transition hover:bg-[#2d6532] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#35783C]/40 sm:text-sm"
                >
                  Siguiente →
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );

  return createPortal(ui, document.body);
}
