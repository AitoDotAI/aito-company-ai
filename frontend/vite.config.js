/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: the React app runs on VITE_PORT (the instance's dashboard PORT) and
// proxies /api to the backend on VITE_API_PORT (PORT+1). `./do dev <config>`
// sets both from the instance's COMPANY_AI_PORT; defaults keep a bare
// `npm run dev` working. Build: `vite build` emits to
// ../src/company_ai/web_dist, which FastAPI serves on PORT in production.
const uiPort = parseInt(process.env.VITE_PORT || "5173", 10);
const apiPort = process.env.VITE_API_PORT || "8770";
export default defineConfig({
  plugins: [react()],
  server: {
    port: uiPort,
    proxy: { "/api": `http://127.0.0.1:${apiPort}` },
  },
  build: {
    outDir: "../src/company_ai/web_dist",
    emptyOutDir: true,
  },
  // Frontend unit tests (vitest). jsdom for component rendering; setup wires
  // jest-dom matchers. Run with `npm test` (or `./do test-ui`).
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test-setup.js",
    include: ["src/**/*.test.{js,jsx}"],
  },
});
