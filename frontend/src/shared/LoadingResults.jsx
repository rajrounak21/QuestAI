import "./loading-results.css";

/**
 * Placeholder shown while a SerpApi search runs.
 *
 * SerpApi takes 5-8s for flights and hotels. Without this the page went almost
 * blank - the form stayed, everything below it was behind !loading, and all the
 * user saw was one thin line. A skeleton keeps the layout stable and makes the
 * wait look like work instead of a hang.
 *
 * `estimate` is measured, not guessed: google_flights came back in 0.04-3.2s
 * across runs, so ~4s is the honest number to put in front of someone.
 */
export default function LoadingResults({ label = "Searching", rows = 4, estimate = "~4s" }) {
  return (
    <div className="loading-results" role="status" aria-live="polite">
      <p className="loading-results-head">
        <span className="loading-spinner" />
        {label}
        <span className="loading-results-est">{estimate}</span>
      </p>
      <div className="loading-results-rows">
        {Array.from({ length: rows }).map((_, i) => (
          <div className="loading-row" key={i}>
            <span className="loading-block loading-block-thumb" />
            <span className="loading-col">
              <span className="loading-block loading-block-line" />
              <span className="loading-block loading-block-line loading-block-short" />
            </span>
            <span className="loading-block loading-block-price" />
          </div>
        ))}
      </div>
    </div>
  );
}