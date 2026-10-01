import { Component, type ErrorInfo, type ReactNode } from "react";

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
    return (
      <Banner tone="critical" title="This view could not be shown">
        <p>
          Something failed while loading it. If the site was updated a moment ago, reloading the page
          fetches the new version; the other views may still work.
        </p>
        <BannerActions>
          <button type="button" className="button" onClick={() => this.setState({ error: null })}>
            Try again
          </button>
          <button type="button" className="button button--ghost" onClick={() => window.location.reload()}>
            Reload the page
          </button>
        </BannerActions>
      </Banner>
    );
  }
}
