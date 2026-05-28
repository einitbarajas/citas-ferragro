import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { useAuth } from "./context/AuthContext";
import LandingPage from "./pages/LandingPage";
const CookieBanner = lazy(() => import("./components/CookieBanner"));
const GuidedTourDialog = lazy(() => import("./components/GuidedTourDialog"));

const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const LoginPage = lazy(() => import("./pages/LoginPage"));

const REDIRECT_TO_LOGIN_KEY = "redirect_to_login";

export default function App() {
  const { session, authReady } = useAuth();
  const [publicView, setPublicView] = useState("landing"); // "landing" | "login" | "register"
  const [showCookieBanner, setShowCookieBanner] = useState(false);
  const [publicGuidedOpen, setPublicGuidedOpen] = useState(false);
  const [publicGuidedIndex, setPublicGuidedIndex] = useState(0);
  const [publicGuidedSteps, setPublicGuidedSteps] = useState([]);

  const closePublicGuidedTour = useCallback(() => {
    setPublicGuidedOpen(false);
  }, []);

  const startPublicTour = useCallback(async () => {
    const { filterAndStripPublicSteps } = await import("./guidedTour/publicSteps");
    const steps = filterAndStripPublicSteps(publicView);
    if (steps.length === 0) return;
    setPublicGuidedSteps(steps);
    setPublicGuidedIndex(0);
    setPublicGuidedOpen(true);
  }, [publicView]);

  useEffect(() => {
    const schedule = window.requestIdleCallback
      ? window.requestIdleCallback(() => setShowCookieBanner(true), { timeout: 4000 })
      : window.setTimeout(() => setShowCookieBanner(true), 2500);
    return () => {
      if (typeof schedule === "number") {
        window.clearTimeout(schedule);
        return;
      }
      if (window.cancelIdleCallback) {
        window.cancelIdleCallback(schedule);
      }
    };
  }, []);

  useEffect(() => {
    if (session) return;
    if (sessionStorage.getItem(REDIRECT_TO_LOGIN_KEY) === "1") {
      setPublicView("login");
      sessionStorage.removeItem(REDIRECT_TO_LOGIN_KEY);
    }
  }, [session]);

  if (!session) {
    return (
      <>
        {publicGuidedOpen ? (
          <Suspense fallback={null}>
            <GuidedTourDialog
              open={publicGuidedOpen}
              label="Manual"
              steps={publicGuidedSteps}
              stepIndex={publicGuidedIndex}
              onStepIndexChange={setPublicGuidedIndex}
              onClose={closePublicGuidedTour}
            />
          </Suspense>
        ) : null}
        {publicView === "landing" ? (
          <LandingPage onLogin={() => setPublicView("login")} onRegister={() => setPublicView("register")} onStartTour={startPublicTour} />
        ) : (
          <Suspense fallback={<div className="flex min-h-screen items-center justify-center bg-slate-50 text-slate-600">Cargando…</div>}>
            {publicView === "login" && (
              <LoginPage initialMode="login" onBack={() => setPublicView("landing")} showInfoPanel={false} onStartTour={startPublicTour} />
            )}
            {publicView === "register" && (
              <LoginPage initialMode="register" onBack={() => setPublicView("landing")} showInfoPanel={false} onStartTour={startPublicTour} />
            )}
          </Suspense>
        )}
        {showCookieBanner ? (
          <Suspense fallback={null}>
            <CookieBanner />
          </Suspense>
        ) : null}
      </>
    );
  }

  if (!authReady) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 text-slate-700">
        <p className="text-sm font-medium">Preparando tu sesión…</p>
      </main>
    );
  }

  return (
    <>
      <Suspense fallback={<div className="flex min-h-screen items-center justify-center bg-slate-50 text-slate-600">Cargando panel…</div>}>
        <DashboardPage />
      </Suspense>
      {showCookieBanner ? (
        <Suspense fallback={null}>
          <CookieBanner />
        </Suspense>
      ) : null}
    </>
  );
}
