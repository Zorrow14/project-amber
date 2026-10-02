import { Component, type ContextType, type ErrorInfo, type ReactNode } from "react";

import { I18nContext } from "../i18n/context";
import { Banner, BannerActions } from "./Banner";

interface Props {
  /** Changing this (e.g. the current view) clears a caught error. */
  resetKey: string;
  children: ReactNode;
}

/**
 * Catches a view that fails to render or whose code chunk fails to load (most
 * often right after a redeploy), so one broken view never blanks the app.
 */
export class ErrorBoundary extends Component<Props, { error: Error | null }> {
  static contextType = I18nContext;
  declare context: ContextType<typeof I18nContext>;
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Amber view failed", error, info.componentStack);
  }

  componentDidUpdate(previous: Props) {
    if (previous.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null });
  }

  render() {
    if (!this.state.error) return this.props.children;
    const { t } = this.context;
    return (
      <Banner tone="critical" title={t("errors.viewTitle")} kind="error">
        <p>{t("errors.viewBody")}</p>
        <BannerActions>
          <button type="button" className="button" onClick={() => this.setState({ error: null })}>
            {t("errors.tryAgain")}
          </button>
          <button type="button" className="button button--ghost" onClick={() => window.location.reload()}>
            {t("errors.reload")}
          </button>
        </BannerActions>
      </Banner>
    );
  }
}
