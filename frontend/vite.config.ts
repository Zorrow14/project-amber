import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  build: {
    sourcemap: true,
    rolldownOptions: {
      output: {
        // Vendor code in its own long-lived chunks: an app change then re-downloads
        // only the app's few kB, not React and Recharts. Recharts stays lazy - only
        // the views import it.
        codeSplitting: {
          groups: [
            { name: "react", test: /node_modules[\\/](react|react-dom|scheduler)[\\/]/, priority: 2 },
            { name: "charts", test: /node_modules[\\/]/, priority: 1 },
          ],
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    // Pre-bundle Recharts: transformed module by module it takes ~20 s to import.
    deps: { optimizer: { client: { enabled: true, include: ["recharts"] } } },
  },
});
