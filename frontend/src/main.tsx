import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { MetaProvider } from "./context/meta";
import { loadCatalog } from "./i18n/catalog";
import { preferredLocale } from "./i18n/detect";
import { I18nProvider } from "./i18n/I18nProvider";
import { ThemeProvider } from "./theme/ThemeProvider";
import "@fontsource-variable/inter/wght.css";
import "./styles/fonts.css";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/components.css";

const root = document.getElementById("root");
if (!root) throw new Error("index.html is missing #root");

// A reader whose browser prefers Burmese: fetch its catalog now, in parallel
// with GET /meta, so the first screen after boot is already in Burmese.
const initial = preferredLocale();
if (initial !== "en") {
  loadCatalog(initial).catch(() => {
    // I18nProvider retries the load, and falls back to English if it fails again.
  });
}

createRoot(root).render(
  <StrictMode>
    <ThemeProvider>
      <I18nProvider initialLocale={initial}>
        <MetaProvider>
          <App />
        </MetaProvider>
      </I18nProvider>
    </ThemeProvider>
  </StrictMode>,
);
