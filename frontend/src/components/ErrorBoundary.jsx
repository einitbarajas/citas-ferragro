import { Component } from "react";

/**
 * Captura errores de render / ciclo de vida y evita la pantalla en blanco.
 * No captura: handlers de eventos, código async suelto, errores dentro del propio boundary.
 */
export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("[ErrorBoundary]", error, info?.componentStack);
  }

  render() {
    const { error } = this.state;
    if (!error) {
      return this.props.children;
    }

    const message = error?.message || String(error);
    const stack = typeof error?.stack === "string" ? error.stack : "";

    return (
      <div className="min-h-screen bg-slate-100 px-4 py-10 text-slate-800">
        <div className="mx-auto max-w-lg rounded-xl border border-rose-200 bg-white p-6 shadow-lg">
          <h1 className="text-lg font-semibold text-rose-800">Algo salió mal</h1>
          <p className="mt-2 text-sm text-slate-600">
            La aplicación encontró un error y no pudo mostrar esta pantalla. Puedes recargar la página o volver atrás en el
            navegador.
          </p>
          <p className="mt-4 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 font-mono text-xs text-slate-800">
            {message}
          </p>
          {stack ? (
            <details className="mt-3 rounded-md border border-amber-200 bg-amber-50 text-slate-800">
              <summary className="cursor-pointer px-3 py-2 text-sm font-medium text-amber-900">Detalle técnico (pila)</summary>
              <pre className="max-h-56 overflow-auto border-t border-amber-200/80 p-3 text-[11px] leading-snug">{stack}</pre>
            </details>
          ) : null}
          <div className="mt-6 flex flex-wrap gap-2">
            <button
              type="button"
              className="rounded-lg bg-[#35783C] px-4 py-2 text-sm font-medium text-white transition hover:bg-[#2d6632] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#35783C]/50"
              onClick={() => window.location.reload()}
            >
              Recargar página
            </button>
            <button
              type="button"
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400/40"
              onClick={() => this.setState({ error: null })}
            >
              Intentar de nuevo
            </button>
          </div>
        </div>
      </div>
    );
  }
}
