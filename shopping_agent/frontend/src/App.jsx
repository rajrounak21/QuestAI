import { useState, useMemo } from 'react';
import { Zap, SlidersHorizontal } from 'lucide-react';
import ShoppingSearch from './components/ShoppingSearch';
import ShoppingCard from './components/ShoppingCard';
import ShoppingFilters, { deriveBrandForFilter } from './components/ShoppingFilters';
import SearchProgress from './components/SearchProgress';
import EmptyState from './components/EmptyState';
import { searchShopping } from './api/shopping';
import './App.css';

const DEFAULT_FILTERS = {
  brands: [],
  stores: [],
  minPrice: null,
  maxPrice: null,
  minRating: 'any',
  sortBy: 'relevance',
};

function App() {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [followUp, setFollowUp] = useState(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [filters, setFilters] = useState({ ...DEFAULT_FILTERS });

  const handleSearch = async (query) => {
    setLoading(true);
    setError(null);
    setFollowUp(null);
    setProducts([]);
    setHasSearched(true);
    setFilters({ ...DEFAULT_FILTERS });

    try {
      const result = await searchShopping(query);
      if (result.error) {
        setError(result.error);
      } else if (result.follow_up_question) {
        setFollowUp(result.follow_up_question);
      } else {
        setProducts(result.products || []);
      }
    } catch (err) {
      console.error('Shopping search failed:', err);
      const msg = err.response?.data?.detail || err.response?.data?.error || err.message;
      setError(msg || 'Shopping search is temporarily unavailable. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const priceBounds = useMemo(() => {
    if (products.length === 0) return { min: 0, max: 100000 };
    const vals = products.map((p) => p.price).filter((v) => typeof v === 'number' && v > 0);
    if (vals.length === 0) return { min: 0, max: 100000 };
    return { min: Math.floor(Math.min(...vals)), max: Math.ceil(Math.max(...vals)) };
  }, [products]);

  const filteredProducts = useMemo(() => {
    let res = [...products];

    if (filters.brands && filters.brands.length > 0) {
      res = res.filter((p) => filters.brands.includes(deriveBrandForFilter(p)));
    }
    if (filters.stores && filters.stores.length > 0) {
      res = res.filter((p) => filters.stores.includes((p.store || '').trim() || 'Unknown'));
    }

    const allCurrencies = new Set(products.map((p) => p.currency).filter(Boolean));
    const mixed = allCurrencies.size > 1;
    if (!mixed) {
      if (filters.minPrice != null) {
        res = res.filter((p) => typeof p.price === 'number' && p.price >= filters.minPrice);
      }
      if (filters.maxPrice != null) {
        res = res.filter((p) => typeof p.price === 'number' && p.price <= filters.maxPrice);
      }
    }

    if (filters.minRating && filters.minRating !== 'any') {
      const thr = parseFloat(filters.minRating);
      res = res.filter((p) => typeof p.rating === 'number' && p.rating >= thr);
    }

    switch (filters.sortBy) {
      case 'price_asc':
        res.sort((a, b) => a.price - b.price);
        break;
      case 'price_desc':
        res.sort((a, b) => b.price - a.price);
        break;
      case 'rating_desc':
        res.sort((a, b) => (b.rating ?? -1) - (a.rating ?? -1));
        break;
      default:
        break;
    }
    return res;
  }, [products, filters]);

  return (
    <div className="app">
      <header className="app-header premium">
        <div className="header-inner">
          <div className="brand">
            <div className="brand-mark"><Zap size={18} fill="white" stroke="white" /></div>
            <div>
              <h1>QuestAI</h1>
              <p className="header-sub">Shopping · India</p>
            </div>
          </div>
          <div className="header-pill">Google Shopping • Live</div>
        </div>
      </header>

      <main className="app-main">
        <ShoppingSearch onSearch={handleSearch} loading={loading} />
        <SearchProgress loading={loading} />

        {error && <EmptyState error={error} />}
        {followUp && <EmptyState followUp={followUp} />}

        {!loading && !error && !followUp && hasSearched && products.length === 0 && (
          <EmptyState />
        )}

        {!loading && products.length > 0 && (
          <div className="results-container">
            <div className="results-sidebar">
              <ShoppingFilters products={products} filters={filters} onFilterChange={setFilters} priceBounds={priceBounds} />
            </div>
            <div className="results-main">
              <div className="results-toolbar">
                <div className="results-count">
                  <span className="count-strong">{filteredProducts.length}</span> of {products.length} products
                  {filters.brands.length > 0 || filters.stores.length > 0 ? <span className="filtered-dot">• filtered</span> : null}
                </div>
                <div className="toolbar-actions">
                  <span className="toolbar-label">Sort:</span>
                  <select
                    value={filters.sortBy}
                    onChange={(e) => setFilters({ ...filters, sortBy: e.target.value })}
                    className="toolbar-select"
                  >
                    <option value="relevance">Relevance</option>
                    <option value="price_asc">Low → High</option>
                    <option value="price_desc">High → Low</option>
                    <option value="rating_desc">Top Rated</option>
                  </select>
                </div>
              </div>
              {filteredProducts.length === 0 ? (
                <div className="no-results premium"><SlidersHorizontal size={16} /> No products match your filters. Clear or adjust price/rating.</div>
              ) : (
                <div className="shopping-grid">
                  {filteredProducts.map((product) => (
                    <ShoppingCard key={product.id} product={product} />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {!hasSearched && !loading && (
          <div className="hero-empty">
            <h2>Find your next favourite product</h2>
            <p>Search from 40+ live Google Shopping results. Filter by brand, store, price & rating — instantly.</p>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
