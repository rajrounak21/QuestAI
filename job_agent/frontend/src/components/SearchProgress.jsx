export default function SearchProgress({ loading, steps = [] }) {
  if (!loading) return null
  return (
    <div className="search-progress">
      <div className="progress-header"><span className="spinner" /> Searching Google Jobs…</div>
      {steps.length > 0 && (
        <div className="progress-steps">
          {steps.map((s, i) => <div key={i} className="progress-step">{s}</div>)}
        </div>
      )}
      <div className="skeleton-grid">
        {Array.from({ length: 6 }).map((_, i) => <div key={i} className="skeleton-card" />)}
      </div>
    </div>
  )
}
