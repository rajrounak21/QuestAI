/**
 * BrandMark — correct logo utilization.
 * - Small contexts (navbar): square `favicon.svg` icon + gradient "AI" wordmark.
 * - Wide contexts (footer/CTA): full `logo.png` lockup with screen-blend
 *   so its black background melts into the dark theme.
 */
export function BrandMark({ size = 32 }) {
  return (
    <a className="brand" href="#top" aria-label="QuestAI home">
      <span className="brand-icon" style={{ width: size, height: size }}>
        <img src={`${import.meta.env.BASE_URL}favicon.svg`} alt="" width={size} height={size} draggable="false" />
      </span>
      <span className="brand-word">
        Quest<span className="brand-ai">AI</span>
      </span>
    </a>
  );
}

export function BrandLockup({ className = "", style }) {
  return (
    <img
      className={`brand-lockup ${className}`.trim()}
      style={style}
      src={`${import.meta.env.BASE_URL}logo.png`}
      alt="QuestAI — One AI Superapp"
      loading="lazy"
      draggable="false"
    />
  );
}
