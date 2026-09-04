import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Served under /app/ so Django can host the build alongside the API.
export default defineConfig({
  base: "/app/",
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/healthz": "http://localhost:8000",
    },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
