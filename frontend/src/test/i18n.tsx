import type { ReactNode } from "react";

import { I18nProvider } from "../i18n/I18nProvider";
import my from "../i18n/locales/my.json";

/** Render `ui` in Burmese, its catalog already loaded (no lazy fetch to wait on). */
export function InBurmese({ children }: { children: ReactNode }) {
  return (
    <I18nProvider initialLocale="my" catalogs={{ my }}>
      {children}
    </I18nProvider>
  );
}
