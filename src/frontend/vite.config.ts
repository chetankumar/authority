import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The backend serves the build from dist/ in production (same-origin). In dev,
// Vite proxies /api to the backend so the same fetch paths work either way.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8700",
    },
  },
  build: {
    outDir: "dist",
  },
});
