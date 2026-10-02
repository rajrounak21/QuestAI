const ITEMS = [
  "Deep Research", "Flight Planning", "Price Comparison", "Job Alerts",
  "Evidence Validation", "Trip Itineraries", "Resume Matching", "Source Discovery",
];

export default function Marquee() {
  const row = [...ITEMS, ...ITEMS];
  return (
    <div className="marquee" aria-hidden="true">
      <div className="marquee-track">
        {row.map((t, i) => (
          <span key={i}>{t} <i className="mq-dot" aria-hidden="true" /></span>
        ))}
      </div>
    </div>
  );
}
