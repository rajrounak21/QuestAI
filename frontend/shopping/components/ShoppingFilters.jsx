import { useEffect, useMemo, useState } from 'react';
import { SlidersHorizontal, Store, Tag, BadgeDollarSign, Star, ChevronUp, ChevronDown } from 'lucide-react';

const GENERIC_BRAND_TOKENS = new Set([
  'buy','refurbished','renewed','used','new','sale','best','cheap','original','for','the','a','an','latest','hot','deal','offer','combo','pack','set','free','with','freebie','gift','pink','raven','dark','light','galaxy','phone','smartphone','mobile','cover','case','ultra','plus','pro','max','5g','4g','lite','mini','standard','edition'
]);

function displayBrand(brandKey) {
  return brandKey.charAt(0).toUpperCase() + brandKey.slice(1).toLowerCase();
}
function deriveBrand(product) {
  if (product.brand) return displayBrand(product.brand.trim().toLowerCase());
  const title = (product.title || '').trim();
  if (!title) return 'Unknown';
  const tokens = title.split(/\s+/).map(t => t.replace(/[^A-Za-z0-9]/g, '')).filter(Boolean);
  for (const tok of tokens) {
    const lower = tok.toLowerCase();
    if (!GENERIC_BRAND_TOKENS.has(lower) && tok.length > 1) {
      return displayBrand(lower);
    }
  }
  return tokens[0] ? displayBrand(tokens[0].toLowerCase()) : 'Unknown';
}

function Accordion({ title, icon: Icon, count, defaultOpen=true, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="filter-section accordion">
      <button className="accordion-head" onClick={() => setOpen(!open)} type="button">
        <span className="accordion-title"><Icon size={14} /> {title} {count!=null && <span className="head-count">{count}</span>}</span>
        <ChevronUp size={14} className={`chev ${open ? 'open' : ''}`} />
      </button>
      {open && <div className="accordion-body">{children}</div>}
    </div>
  );
}

export default function ShoppingFilters({ products, filters, onFilterChange, priceBounds, currencySymbol = '₹', numberLocale = 'en-IN' }) {
  const [showAllBrands, setShowAllBrands] = useState(false);
  const [showAllStores, setShowAllStores] = useState(false);
  const [masterOpen, setMasterOpen] = useState(true);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const check = () => {
      const mobile = window.matchMedia('(max-width: 980px)').matches;
      setIsMobile(mobile);
      setMasterOpen(!mobile);
    };
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);

  const brands = useMemo(() => {
    const counts = {};
    products.forEach((p) => {
      const b = deriveBrand(p);
      if (!b || b === 'Unknown') {
        counts['Unknown'] = (counts['Unknown'] || 0) + 1;
        return;
      }
      counts[b] = (counts[b] || 0) + 1;
    });
    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .map(([name, count]) => ({ name, count }));
  }, [products]);

  const stores = useMemo(() => {
    const counts = {};
    products.forEach((p) => {
      const s = (p.store || '').trim() || 'Unknown';
      counts[s] = (counts[s] || 0) + 1;
    });
    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .map(([name, count]) => ({ name, count }));
  }, [products]);

  const currencies = useMemo(() => new Set(products.map((p) => p.currency).filter(Boolean)), [products]);
  const mixedCurrency = currencies.size > 1;

  const visibleBrands = showAllBrands ? brands : brands.slice(0, 8);
  const visibleStores = showAllStores ? stores : stores.slice(0, 8);

  const handleBrandToggle = (brand) => {
    const cur = filters.brands || [];
    const updated = cur.includes(brand) ? cur.filter((b) => b !== brand) : [...cur, brand];
    onFilterChange({ ...filters, brands: updated });
  };

  const handleStoreToggle = (store) => {
    const cur = filters.stores || [];
    const updated = cur.includes(store) ? cur.filter((s) => s !== store) : [...cur, store];
    onFilterChange({ ...filters, stores: updated });
  };

  const handleMinPriceChange = (val) => {
    const num = val === '' ? null : Number(val);
    onFilterChange({ ...filters, minPrice: Number.isFinite(num) ? num : null });
  };

  const handleMaxPriceChange = (val) => {
    const num = val === '' ? null : Number(val);
    onFilterChange({ ...filters, maxPrice: Number.isFinite(num) ? num : null });
  };

  const handleMinPriceSlider = (e) => {
    const v = Number(e.target.value);
    onFilterChange({ ...filters, minPrice: v });
  };

  const handleMaxPriceSlider = (e) => {
    const v = Number(e.target.value);
    onFilterChange({ ...filters, maxPrice: v });
  };

  const handleRatingChange = (val) => onFilterChange({ ...filters, minRating: val });
  const handleClear = () => onFilterChange({ brands: [], stores: [], minPrice: null, maxPrice: null, minRating: 'any', sortBy: 'relevance' });

  const activeCount = (filters.brands?.length||0)+(filters.stores?.length||0)+(filters.minPrice!=null?1:0)+(filters.maxPrice!=null?1:0)+(filters.minRating!=='any'?1:0);

  const minBound = priceBounds?.min ?? 0;
  const maxBound = priceBounds?.max ?? 100000;
  const curMin = filters.minPrice ?? minBound;
  const curMax = filters.maxPrice ?? maxBound;

  return (
    <div className="shopping-filters premium">
      <button type="button" className="filters-master-toggle" onClick={() => setMasterOpen(!masterOpen)} aria-expanded={masterOpen}>
        <span className="master-left"><SlidersHorizontal size={16} /> Filters {activeCount>0 && <span className="active-badge">{activeCount}</span>} <span className="master-count">{products.length} items</span></span>
        <span className="master-right">
          {activeCount>0 && <span className="clear-filters-btn pill" onClick={(e) => { e.stopPropagation(); handleClear(); }}>Clear</span>}
          {masterOpen ? <ChevronUp size={16} className="master-chev" /> : <ChevronDown size={16} className="master-chev" />}
        </span>
      </button>
      {/* Desktop always shows header bar too for PC layout, mobile uses master toggle only */}
      <div className="filters-header desktop-only">
        <h3><SlidersHorizontal size={15} /> Filters {activeCount>0 && <span className="active-badge">{activeCount}</span>}</h3>
        {activeCount>0 && <button className="clear-filters-btn" onClick={handleClear}>Clear</button>}
      </div>

      <div className={`filters-body ${masterOpen ? 'open' : 'collapsed'}`}>

      <Accordion title="Brand" icon={Tag} count={brands.length}>
        {brands.length === 0 ? <p className="filter-empty">No brands</p> : (
          <>
            {visibleBrands.map(({ name, count }) => (
              <label key={name} className={`filter-option premium ${ (filters.brands||[]).includes(name) ? 'checked' : ''}`}>
                <input type="checkbox" checked={(filters.brands || []).includes(name)} onChange={() => handleBrandToggle(name)} />
                <span className="filter-label">{name}</span>
                <span className="filter-count">{count}</span>
              </label>
            ))}
            {brands.length > 8 && (
              <button className="show-more-btn" onClick={() => setShowAllBrands(!showAllBrands)}>
                {showAllBrands ? 'Show less' : `+ ${brands.length - 8} more`}
              </button>
            )}
          </>
        )}
      </Accordion>

      <Accordion title="Store" icon={Store} count={stores.length}>
        {stores.length === 0 ? <p className="filter-empty">No stores</p> : (
          <>
            {visibleStores.map(({ name, count }) => (
              <label key={name} className={`filter-option premium ${ (filters.stores||[]).includes(name) ? 'checked' : ''}`}>
                <input type="checkbox" checked={(filters.stores || []).includes(name)} onChange={() => handleStoreToggle(name)} />
                <span className="filter-label">{name}</span>
                <span className="filter-count">{count}</span>
              </label>
            ))}
            {stores.length > 8 && (
              <button className="show-more-btn" onClick={() => setShowAllStores(!showAllStores)}>
                {showAllStores ? 'Show less' : `+ ${stores.length - 8} more`}
              </button>
            )}
          </>
        )}
      </Accordion>

      <Accordion title="Price" icon={BadgeDollarSign}>
        {mixedCurrency ? (
          <p className="filter-warning">Multiple currencies — price filter disabled.</p>
        ) : (
          <>
            <div className="price-inputs premium">
              <div className="price-input-group">
                <label>Min</label>
                <div className="input-with-symbol"><span>{currencySymbol}</span><input type="number" min={minBound} max={maxBound} value={filters.minPrice ?? ''} placeholder={String(minBound)} onChange={(e) => handleMinPriceChange(e.target.value)} /></div>
              </div>
              <span className="price-sep">—</span>
              <div className="price-input-group">
                <label>Max</label>
                <div className="input-with-symbol"><span>{currencySymbol}</span><input type="number" min={minBound} max={maxBound} value={filters.maxPrice ?? ''} placeholder={String(maxBound)} onChange={(e) => handleMaxPriceChange(e.target.value)} /></div>
              </div>
            </div>
            <div className="price-sliders premium">
              <div className="slider-row"><span className="slider-label">Min</span><input type="range" min={minBound} max={maxBound} value={curMin} onChange={handleMinPriceSlider} /></div>
              <div className="slider-row"><span className="slider-label">Max</span><input type="range" min={minBound} max={maxBound} value={curMax} onChange={handleMaxPriceSlider} /></div>
            </div>
            <div className="range-labels">
              <span>{currencySymbol}{minBound.toLocaleString(numberLocale)}</span>
              <span>{currencySymbol}{maxBound.toLocaleString(numberLocale)}</span>
            </div>
          </>
        )}
      </Accordion>

      <Accordion title="Rating" icon={Star}>
        <div className="rating-options">
          {[
            {v:'any', label:'Any rating'},
            {v:'4', label:'4.0+ and above'},
            {v:'3', label:'3.0+ and above'},
          ].map(o=> (
            <label key={o.v} className={`filter-option premium radio ${filters.minRating===o.v ? 'checked' : ''}`}>
              <input type="radio" name="rating" value={o.v} checked={filters.minRating===o.v} onChange={() => handleRatingChange(o.v)} />
              <Star size={12} fill={filters.minRating===o.v ? '#f59e0b' : 'none'} stroke={filters.minRating===o.v ? '#f59e0b' : '#94a3b8'} /> {o.label}
            </label>
          ))}
        </div>
      </Accordion>
      </div>
    </div>
  );
}

export function deriveBrandForFilter(product) {
  return deriveBrand(product);
}
