import "./loading-results.css";

/**
 * Placeholder shown while a SerpApi search runs.
 *
 * SerpApi takes 5-8s for flights and hotels. Without this the page went almost
 * blank - the form stayed, everything below it was behind !loading, and all the
 * user saw was one thin line. A skeleton keeps the layout stable and makes the
 * wait look like work instead of a hang.
 */
export default function LoadingResults({ label = "Searching", rows = 4 }) {
  return (
    <div className="loading-results" role="status" aria-live="polite">
      <p className="loading-results-head">
        <span className="dot-pulse" />
        {label}
      </p>
      <div className="loading-results-rows">
        {Array.from({ length: rows }).map((_, i) => (
          <div className="loading-row" key={i} style={{ animationDelay: `${i * 0.08}s` }}>
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