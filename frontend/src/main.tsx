import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { RouteProvider } from "./context/route";
import { loadCatalog } from "./i18n/catalog";
import { preferredLocale } from "./i18n/detect";
import { I18nProvider } from "./i18n/I18nProvider";
import { parseLocation } from "./lib/url";
import { ThemeProvider } from "./theme/ThemeProvider";
import "@fontsource-variable/inter/wght.css";
import "./styles/fonts.css";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/components.css";

const root = document.getElementById("root");
if (!root) throw new Error("index.html is missing #root");

// The language a shared link names, else the browser's. If it is Burmese, fetch
// its catalog now, in parallel with GET /meta, so the first screen is in Burmese.
const initial = parseLocation(window.location.search, window.location.hash).lang ?? preferredLocale();
if (initial !== "en") {
  loadCatalog(initial).catch(() => {
    // I18nProvider retries the load, and falls back to English if it fails again.
  });
}

createRoot(root).render(
  <StrictMode>
    <ThemeProvider>
      <I18nProvider initialLocale={initial}>
        <RouteProvider>
          <App />
        </RouteProvider>
      </I18nProvider>
    </ThemeProvider>
  </StrictMode>,
);
