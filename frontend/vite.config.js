import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, "..", "");
  const apiTarget = (env.VITE_DEV_API_PROXY || "http://127.0.0.1:8000").replace(/\/$/, "");
  const apiOrigin = (env.VITE_API_URL || "").trim().replace(/\/$/, "");
  const isDev = mode === "development";
  const connectSrc = isDev
    ? "connect-src 'self' http://localhost:8000 http://127.0.0.1:8000 ws://localhost:* ws://127.0.0.1:*"
    : apiOrigin
      ? `connect-src 'self' ${apiOrigin}`
      : "connect-src 'self' https://*.onrender.com";
  const cspDirectives = [
    "default-src 'self'",
    // En desarrollo Vite usa runtime/HMR que puede requerir inline/eval.
    // En build/preview mantenemos CSP estricta para producción.
    isDev ? "script-src 'self' 'unsafe-inline' 'unsafe-eval'" : "script-src 'self'",
    isDev ? "style-src 'self' 'unsafe-inline'" : "style-src 'self'",
    "img-src 'self' data: https://res.cloudinary.com",
    connectSrc,
    "font-src 'self' data:",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ];
  const securityHeaders = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
  };

  return {
    // En algunos entornos (proxy/escáner/extensión) se inyecta una CSP externa
    // que bloquea el preamble inline del plugin React en dev.
    // Evitamos ese preamble en desarrollo y mantenemos el plugin en build.
    plugins: isDev ? [] : [react({ fastRefresh: false })],
    esbuild: isDev
      ? {
          // En dev sin plugin-react: usar runtime automático de JSX para evitar
          // errores "React is not defined" sin depender de import manual.
          jsx: "automatic",
        }
      : undefined,
    envDir: "..",
    build: {
      target: "es2020",
      cssCodeSplit: true,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes("node_modules")) {
              if (id.includes("node_modules/react-dom") || id.includes("node_modules/react/")) {
                return "vendor-react-runtime";
              }
              if (id.includes("axios")) return "vendor-axios";
              return undefined;
            }
            if (id.includes("/guidedTour/")) return "guided-tour";
            if (id.includes("/components/Appointment")) return "appointments-ui";
            return undefined;
          },
        },
      },
    },
    server: {
      host: "0.0.0.0",
      port: 2711,
      strictPort: false,
      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true,
        },
        "/health": {
          target: apiTarget,
          changeOrigin: true,
        },
      },
      headers: securityHeaders,
    },
    preview: {
      host: "0.0.0.0",
      port: 2711,
      strictPort: false,
      proxy: {
        "/api": { target: apiTarget, changeOrigin: true },
        "/health": { target: apiTarget, changeOrigin: true },
      },
      headers: securityHeaders,
    },
  };
});
