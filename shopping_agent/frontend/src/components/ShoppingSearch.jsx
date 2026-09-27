import { useState } from 'react';
import { Search, ArrowRight, Sparkles } from 'lucide-react';

const suggestions = ['iPhone 15', 'Samsung S22', 'Nike shoes', 'Wireless headphones', 'MacBook Air'];

export default function ShoppingSearch({ onSearch, loading }) {
  const [query, setQuery] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    onSearch(query.trim());
  };

  return (
    <div className="search-hero">
      <form className="shopping-search" onSubmit={handleSubmit}>
        <div className="search-row">
          <div className="search-input-wrap">
            <Search size={18} className="search-icon" color="#94a3b8" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search for products"
              className="shopping-input"
              disabled={loading}
            />
          </div>
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
            <button key={s} type="button" className="sugg-chip" onClick={() => { setQuery(s); onSearch(s); }} disabled={loading}>{s}</button>
          ))}
        </div>
        <p className="search-hint"><span className="dot-pulse" /> Live from Google Shopping · India · 40+ results in ~3s</p>
      </form>
    </div>
  );
}
