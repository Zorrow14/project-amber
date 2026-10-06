import react from "@vitejs/plugin-react";
import { loadEnv, type Plugin } from "vite";
import { defineConfig } from "vitest/config";

/**
 * The deployed origin, for the share card's absolute URLs: link-preview crawlers
 * do not resolve relative ones. Set VITE_SITE_URL to build for another domain.
 */
const DEFAULT_SITE_URL = "https://amber-sim.vercel.app";

/** Fills `%AMBER_SITE_URL%` in index.html (the Open Graph and Twitter card tags). */
function siteUrl(origin: string): Plugin {
  return {
    name: "amber-site-url",
    transformIndexHtml: (html) => html.replaceAll("%AMBER_SITE_URL%", origin),
  };
}

export default defineConfig(({ mode }) => {
  const origin = (loadEnv(mode, process.cwd(), "VITE_").VITE_SITE_URL || DEFAULT_SITE_URL).replace(/\/+$/, "");
  return {
    plugins: [react(), siteUrl(origin)],
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
              // Everything else vendored is Recharts and its deps - except the font CSS,
              // which must ship with the entry so the first paint is already set in Inter.
              { name: "charts", test: /node_modules[\\/](?!@fontsource)/, priority: 1 },
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
  };
});
