import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { MetaProvider } from "./context/meta";
import { ThemeProvider } from "./theme/ThemeProvider";
import "@fontsource-variable/inter/wght.css";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/components.css";

const root = document.getElementById("root");
if (!root) throw new Error("index.html is missing #root");

createRoot(root).render(
  <StrictMode>
    <ThemeProvider>
      <MetaProvider>
        <App />
      </MetaProvider>
    </ThemeProvider>
  </StrictMode>,
);
