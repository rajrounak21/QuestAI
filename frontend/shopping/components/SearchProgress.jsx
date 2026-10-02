import { Loader2 } from 'lucide-react';

export default function SearchProgress({ loading, locationLabel }) {
  if (!loading) return null;
  return (
    <div className="search-progress premium">
      <div className="progress-header">
        <Loader2 size={18} className="spinner" />
        <span>Searching Google Shopping + Amazon for you...</span>
        <span className="progress-sub">{locationLabel || 'India'} · ~3s</span>
      </div>
      <div className="skeleton-grid">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="skeleton-card">
            <div className="skeleton-img shimmer" />
            <div className="skeleton-line shimmer" style={{ width: '85%' }} />
            <div className="skeleton-line shimmer" style={{ width: '60%' }} />
            <div className="skeleton-line shimmer" style={{ width: '40%' }} />
          </div>
        ))}
      </div>
    </div>
  );
}
