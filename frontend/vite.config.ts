import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Served at / so Django can host the build alongside the API.
export default defineConfig({
  base: "/",
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/healthz": "http://localhost:8000",
      // Django-owned routes. Without these the SPA catch-all answers instead,
      // and a task's site or the live view silently renders the landing page.
      "/sites": "http://localhost:8000",
      "/live": "http://localhost:8000",
    },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
