import { useEffect, useRef, useState } from 'react';
import { Search, ArrowRight, Sparkles, MapPin } from 'lucide-react';

const suggestions = ['iPhone 15', 'Samsung S22', 'Nike shoes', 'Wireless headphones', 'MacBook Air'];

export default function ShoppingSearch({ onSearch, loading, locations, location, onLocationChange, locationLabel, initialQuery = '' }) {
  const [query, setQuery] = useState(initialQuery);
  const inputRef = useRef(null);

  // A question handed over from the dashboard (/shopping?q=...) lands here as
  // text only. It must never search on its own — the user presses Search.
  useEffect(() => {
    if (initialQuery) setQuery(initialQuery);
  }, [initialQuery]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    onSearch(query.trim());
  };

  const fillSuggestion = (s) => {
    // Pre-fill only. This used to call onSearch(s) as well, so a single tap on
    // a suggestion ran a live search the user never asked for.
    setQuery(s);
    inputRef.current?.focus();
  };

  return (
    <div className="search-hero">
      <form className="shopping-search" onSubmit={handleSubmit}>
        <div className="search-row">
          <div className="search-input-wrap">
            <Search size={18} className="search-icon" color="#94a3b8" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search for products"
              className="shopping-input"
              disabled={loading}
            />
          </div>
          <label className="location-pick" title="Shopping location">
            <MapPin size={14} />
            <select value={location} onChange={(e) => onLocationChange(e.target.value)} disabled={loading} aria-label="Shopping location">
              {(locations || []).map((l) => (
                <option key={l.code} value={l.code}>{l.label}</option>
              ))}
            </select>
          </label>
          <button type="submit" disabled={loading || !query.trim()} className="search-btn">
            {loading ? (
              <span className="btn-loading"><span className="spinner-small" /> Searching</span>
            ) : (
              <>Search <ArrowRight size={16} /></>
            )}
          </button>
        </div>
        <div className="search-suggestions">
          <span className="sugg-label"><Sparkles size={12} /> Try:</span>
          {suggestions.map(s => (
            <button key={s} type="button" className="sugg-chip" onClick={() => fillSuggestion(s)} disabled={loading}>{s}</button>
          ))}
        </div>
        <p className="search-hint"><span className="dot-pulse" /> Live from Google Shopping + Amazon · {locationLabel || 'India'}</p>
      </form>
    </div>
  );
}
