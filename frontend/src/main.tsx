import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { MetaProvider } from "./context/meta";
import "./styles.css";

const root = document.getElementById("root");
if (!root) throw new Error("index.html is missing #root");

createRoot(root).render(
  <StrictMode>
    <MetaProvider>
      <App />
    </MetaProvider>
  </StrictMode>,
);
