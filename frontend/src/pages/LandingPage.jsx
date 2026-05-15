import BrandLogo from "../components/BrandLogo";

export default function LandingPage({ onLogin, onRegister, onStartTour } = {}) {
  return (
    <div className="min-h-screen bg-white">
      <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-2 px-4 py-3 sm:gap-3">
          <div className="min-w-0 flex-1 basis-[min(100%,12rem)] pr-1 py-1 sm:basis-auto">
            <BrandLogo className="max-h-10 w-auto sm:max-h-12" fetchPriority="high" />
          </div>

          <nav aria-label="Acciones de acceso" className="ml-auto flex shrink-0 flex-wrap items-center justify-end gap-1.5 sm:gap-2">
            <button
              type="button"
              onClick={() => (typeof onStartTour === "function" ? onStartTour() : null)}
              data-tour="landing-manual-btn"
              className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-600 transition hover:bg-slate-100"
            >
              Manual
            </button>
            <button
              type="button"
              onClick={() => (typeof onLogin === "function" ? onLogin() : null)}
              data-tour="landing-login-btn"
              className="inline-flex min-h-10 items-center gap-1.5 rounded-lg px-2.5 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-100 sm:gap-2 sm:px-3"
            >
              <svg viewBox="0 0 24 24" className="h-5 w-5 shrink-0 fill-none stroke-current" strokeWidth="2" aria-hidden="true">
                <path d="M20 21a8 8 0 1 0-16 0" />
                <circle cx="12" cy="9" r="4" />
              </svg>
              <span className="hidden sm:inline">Iniciar sesión</span>
            </button>
            <button
              type="button"
              onClick={() => (typeof onRegister === "function" ? onRegister() : null)}
              data-tour="landing-register-btn"
              className="min-h-10 rounded-lg bg-[#2a5c30] px-2.5 py-2 text-xs font-semibold text-white shadow-sm shadow-emerald-900/25 transition hover:bg-[#1f4524] sm:px-3 sm:text-sm"
            >
              Registrarme
            </button>
          </nav>
        </div>

      </header>

      <main>
        <section className="mx-auto w-full max-w-6xl px-4 py-6">
          <div className="grid gap-4 md:grid-cols-2">
            <section
              aria-labelledby="landing-intro-title"
              data-tour="landing-intro"
              className="landing-hero-bg rounded-2xl border border-slate-200 bg-gradient-to-br from-[#35783C] to-[#2d6532] p-6 text-white shadow-lg"
            >
              <p className="text-xs font-semibold uppercase tracking-wide text-white/95">
                Portal de citas
              </p>
              <h1 id="landing-intro-title" className="mt-2 text-2xl font-extrabold leading-tight md:text-3xl">
                Portal para proveedores con gestión clara de entregas.
              </h1>
              <p className="mt-3 text-sm text-white/95">
                Accede al portal para agendar citas de entrega de material, recibir notificaciones sobre cambios y consultar
                el historial de entregas registradas en esta empresa.
              </p>
              <div className="mt-5 rounded-lg bg-black/20 p-3 ring-1 ring-white/15">
                <h2 className="text-sm font-bold text-white">¿De qué trata esta página?</h2>
                <p className="mt-2 text-sm leading-relaxed text-white/95">
                  Este portal para proveedores está orientado exclusivamente a tres funciones: agendar citas de entrega de
                  material, recibir notificaciones cuando se actualice el tiempo de atención o se modifique información
                  relacionada con la cita, y consultar el historial de entregas realizadas únicamente para esta empresa.
                </p>
              </div>
            </section>

            <section aria-labelledby="landing-modules-title" data-tour="landing-modules" className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 id="landing-modules-title" className="text-sm font-semibold text-slate-900">
                Módulos del portal
              </h2>
              <div className="mt-4 grid grid-cols-1 gap-3 min-[400px]:grid-cols-2 sm:grid-cols-3">
                {[
                  "Solicitar cita de entrega",
                  "Notificaciones de cambios",
                  "Historial de entregas en esta empresa",
                ].map((label) => (
                  <button
                    key={label}
                    type="button"
                    className="group rounded-xl border border-slate-200 bg-slate-50 px-3 py-4 text-left text-xs font-semibold text-slate-700 transition hover:border-[#D7D8D8] hover:bg-slate-100"
                  >
                    <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-full bg-[#35783C] text-white transition group-hover:bg-[#2d6532]">
                      <svg
                        viewBox="0 0 24 24"
                        className="h-5 w-5 fill-none stroke-current"
                        strokeWidth="2"
                        aria-hidden="true"
                      >
                        <path d="M4 14c2-3 5-5 8-6 4-1 7 0 8 1-1 4-4 7-8 8-4 1-7 0-8-3z" />
                      </svg>
                    </div>
                    <div className="line-clamp-2">{label}</div>
                  </button>
                ))}
              </div>
              <div className="mt-5 rounded-xl border border-[#D7D8D8] bg-slate-50 p-4" data-tour="landing-contact">
                <p className="text-sm font-semibold text-[#121212]">Información de contacto</p>
                <p className="mt-1 text-sm text-slate-700">
                  Si tienes problemas para ingresar o registrarte, contáctanos.
                </p>
                <div className="mt-3 flex flex-col gap-1 text-sm">
                  <a
                    className="font-medium text-[#1f5a26] underline-offset-2 transition-colors hover:text-[#16401a] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#35783C]/50 focus-visible:ring-offset-2 dark:text-emerald-400 dark:ring-offset-slate-900 dark:hover:text-emerald-200 dark:hover:underline"
                    href="https://wa.me/573142254819"
                  >
                    WhatsApp: +57 3142254819
                  </a>
                  <a
                    className="font-medium text-[#1f5a26] underline-offset-2 transition-colors hover:text-[#16401a] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#35783C]/50 focus-visible:ring-offset-2 dark:text-emerald-400 dark:ring-offset-slate-900 dark:hover:text-emerald-200 dark:hover:underline"
                    href="mailto:ecommerce@ferragro.com"
                  >
                    Correo: ecommerce@ferragro.com
                  </a>
                </div>
              </div>
              <div className="mt-4 rounded-xl border border-[#D7D8D8] bg-white p-4">
                <h3 className="text-sm font-semibold text-[#121212]">Misión y visión corporativa</h3>
                <p className="mt-1 text-sm text-slate-700">
                  Somos una compañía mayorista en productos agro-ferreteros y tecnológicos para el campo, enfocada en
                  calidad de servicio, innovación y especialización de procesos.
                </p>
              </div>
            </section>
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-200">
        <div className="mx-auto w-full max-w-6xl px-4 py-6 text-xs text-slate-500">
          <p>© {new Date().getFullYear()} Ferragro. Todos los derechos reservados.</p>
        </div>
      </footer>
    </div>
  );
}

