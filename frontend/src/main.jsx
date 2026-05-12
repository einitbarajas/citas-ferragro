import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";
import { AuthProvider } from "./context/AuthContext";
import { ThemeProvider } from "./context/ThemeContext";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { initAxe } from "./axe";

const RootWrapper = import.meta.env.DEV ? React.Fragment : React.StrictMode;

const rootEl = document.getElementById("root");
if (!rootEl) {
  document.body.innerHTML =
    '<div style="font-family:system-ui;padding:2rem;max-width:32rem;margin:auto"><h1 style="color:#9f1239">Error</h1><p>No existe el elemento <code>#root</code> en el HTML. Revisa <code>index.html</code>.</p></div>';
} else {
  ReactDOM.createRoot(rootEl).render(
    <RootWrapper>
      <ErrorBoundary>
        <ThemeProvider>
          <AuthProvider>
            <App />
          </AuthProvider>
        </ThemeProvider>
      </ErrorBoundary>
    </RootWrapper>
  );
}

if (import.meta.env.DEV) {
  initAxe().catch(() => {
    // No bloquea el render si la instrumentación de accesibilidad falla en dev.
  });
}
