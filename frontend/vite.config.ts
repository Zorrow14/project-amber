import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  build: { sourcemap: true },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    // Pre-bundle Recharts: transformed module by module it takes ~20 s to import.
    deps: { optimizer: { client: { enabled: true, include: ["recharts"] } } },
  },
});
