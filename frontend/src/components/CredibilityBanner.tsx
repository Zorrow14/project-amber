import { Banner } from "./Banner";

/**
 * The not-credible banner. Rendered wherever a series whose model failed its
 * credibility gate is shown; renders nothing for a credible one. The message
 * comes from the API, so the UI and the chart captions say the same thing.
 */
export function CredibilityBanner({
  credible,
  title,
  message,
}: {
  credible: boolean;
  title: string;
  message: string | null;
}) {
  if (credible) return null;
  return (
    <Banner tone="critical" title={title} kind="credibility">
      <p>{message}</p>
    </Banner>
  );
}
