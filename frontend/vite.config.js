import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, "..", "");
  const apiTarget = (env.VITE_DEV_API_PROXY || "http://127.0.0.1:8000").replace(/\/$/, "");
  const isDev = mode === "development";
  const cspDirectives = [
    "default-src 'self'",
    isDev ? "script-src 'self' 'unsafe-inline' 'unsafe-eval'" : "script-src 'self'",
    isDev ? "style-src 'self' 'unsafe-inline'" : "style-src 'self'",
    "img-src 'self' data: https://res.cloudinary.com",
    isDev
      ? "connect-src 'self' http://localhost:8000 http://127.0.0.1:8000 ws://localhost:* ws://127.0.0.1:*"
      : "connect-src 'self' http://localhost:8000 http://127.0.0.1:8000",
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
    "Cross-Origin-Resource-Policy": "same-site",
    "Content-Security-Policy": `${cspDirectives.join("; ")};`,
  };

  return {
    plugins: [react({ fastRefresh: false })],
    envDir: "..",
    build: {
      target: "es2020",
      cssCodeSplit: true,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (!id.includes("node_modules")) return undefined;
            if (id.includes("node_modules/react-dom")) return "vendor-react-dom";
            if (id.includes("node_modules/react/")) return "vendor-react";
            if (id.includes("axios")) return "vendor-axios";
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
