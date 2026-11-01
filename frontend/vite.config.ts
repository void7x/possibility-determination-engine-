import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server binds all interfaces so the sandbox preview can reach it.
// All API calls are same-origin relative URLs, proxied to the FastAPI backend.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    allowedHosts: true as unknown as string[],
    proxy: {
      "/v1": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/healthz": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
