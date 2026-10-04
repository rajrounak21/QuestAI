import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { SlidersHorizontal, History, Trash2, LayoutGrid, Plus } from "lucide-react";
import ShoppingSearch from "./components/ShoppingSearch";
import ShoppingCard from "./components/ShoppingCard";
import ShoppingFilters, { deriveBrandForFilter } from "./components/ShoppingFilters";
import SearchProgress from "./components/SearchProgress";
import EmptyState from "./components/EmptyState";
import { shoppingApi, timeAgo, LOCATIONS, DEFAULT_LOCATION, locationLabel, currencySymbol, currencyLocale } from "./api";
import { getToken } from "../auth/api";
import { useRouterPrefill } from "../src/shared/useRouterPrefill";
import RouteReceipt from "../src/shared/RouteReceipt";
import "./Shopping.css";

const DEFAULT_FILTERS = {
  brands: [],
  stores: [],
  minPrice: null,
  maxPrice: null,
  minRating: "any",
  sortBy: "relevance",
};

export default function Shopping() {
  const navigate = useNavigate();
  const { sessionId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();

  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [followUp, setFollowUp] = useState(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [filters, setFilters] = useState({ ...DEFAULT_FILTERS });

  // history layer (Mongo persistence behind the same UX)
  const [sessions, setSessions] = useState([]);
  const [sessionTitle, setSessionTitle] = useState("");
  const [lastSearched, setLastSearched] = useState("");
  const [sessionLocation, setSessionLocation] = useState("");

  // shopping location (persisted per browser, sent with every search)
  const [location, setLocation] = useState(
    () => localStorage.getItem("questai_shopping_location") || DEFAULT_LOCATION
  );

  const changeLocation = (code) => {
    setLocation(code);
    localStorage.setItem("questai_shopping_location", code);
  };

  // Question handed over from the dashboard; shown in the search box only.
  const [prefillQuery, setPrefillQuery] = useState("");
  const routerPrefill = useRouterPrefill("shopping");

  const autoRunRef = useRef(false);
  const toastTimer = useRef(null);

  // delete confirm + toast
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [toast, setToast] = useState("");

  // old saves (before the persist-all fix) kept only 30 of N products
  const [partial, setPartial] = useState(null);

  const showToast = (msg) => {
    setToast(msg);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(""), 3000);
  };

  useEffect(() => () => { if (toastTimer.current) clearTimeout(toastTimer.current); }, []);

  const loadHistory = async () => {
    try {
      const data = await shoppingApi.history(20);
      setSessions(data.items || []);
    } catch {
      /* history stays empty, search still works */
    }
  };

  useEffect(() => {
    if (!getToken()) {
      navigate("/login", { replace: true });
      return;
    }
    loadHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const resetResults = () => {
    setProducts([]);
    setError(null);
    setFollowUp(null);
    setHasSearched(false);
    setFilters({ ...DEFAULT_FILTERS });
    setSessionTitle("");
    setLastSearched("");
    setSessionLocation("");
    setPartial(null);
  };

  const handleSearch = async (query, opts = {}) => {
    const q = (query || "").trim();
    if (!q || loading) return;
    setLoading(true);
    setError(null);
    setFollowUp(null);
    setProducts([]);
    setHasSearched(true);
    setFilters({ ...DEFAULT_FILTERS });
    setPartial(null);

    const loc = opts.location || location;
    try {
      const result = opts.again
        ? await shoppingApi.searchAgain(sessionId, q, loc)
        : await shoppingApi.search({ query: q, session_id: sessionId || undefined, location: loc });
      setProducts(result.products || []);
      setSessionTitle(q);
      setLastSearched(new Date().toISOString());
      if (result.location) {
        setSessionLocation(result.location);
        changeLocation(result.location);
      }
      if (result.session_id && result.session_id !== sessionId) {
        navigate(`/shopping/${result.session_id}`, { replace: !sessionId });
      }
      loadHistory();
    } catch (err) {
      if (err.code === "unauthorized") {
        navigate("/login", { replace: true });
        return;
      }
      if (err.code === 422) {
        // backend couldn't parse a product query — same as standalone follow-up
        setFollowUp(err.message);
      } else {
        setError(err.message || "Shopping search is temporarily unavailable. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  // Open saved session from Mongo (zero API cost)
  useEffect(() => {
    if (!sessionId) {
      resetResults();
      return;
    }
    let alive = true;
    setLoading(true);
    shoppingApi
      .getSession(sessionId)
      .then((d) => {
        if (!alive) return;
        const latest = d.latest;
        // See Flights.jsx - session.title is frozen at the first search, so use the
        // latest search row's query instead or the heading contradicts the list.
        setSessionTitle(latest?.query || d.session?.title || d.session?.query || "");
        setLastSearched(d.session?.last_search_at || latest?.created_at || "");
        const sessLoc = d.session?.location || latest?.location || "";
        setSessionLocation(sessLoc);
        // Sync the picker so "Search again" reuses the session's country
        // instead of whatever the global picker was left on.
        if (sessLoc) changeLocation(sessLoc);
        const saved = latest?.products || [];
        setProducts(saved);
        // Old saves (pre persist-all fix) kept only 30 of N — say so honestly
        // instead of showing a conflicting count.
        if (latest && (latest.product_count ?? saved.length) > saved.length) {
          setPartial({ saved: saved.length, total: latest.product_count });
        } else {
          setPartial(null);
        }
        setHasSearched(true);
      })
      .catch((e) => {
        if (!alive) return;
        if (e.code === "unauthorized") navigate("/login", { replace: true });
        else setError(e.message || "Could not load this shopping session.");
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  // ?q= from the dashboard only PREFILLS the form. It used to call
  // handleSearch(q) here, which ran a live search the moment the page opened.
  // The param is still stripped so a refresh can't re-fill over the user's edits.
  useEffect(() => {
    const q = searchParams.get("q");
    if (!q || autoRunRef.current || sessionId) return;
    autoRunRef.current = true;
    setSearchParams({}, { replace: true });
    // The router's extracted query is cleaner than the raw sentence.
    setPrefillQuery(routerPrefill?.fields?.query || q);
    setProducts([]);
    setHasSearched(false);
    setError(null);
    setFollowUp(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, sessionId]);

  const removeSession = async (id, title) => {
    try {
      await shoppingApi.remove(id);
    } catch {
      showToast("Could not delete this session.");
      return;
    }
    if (id === sessionId) navigate("/shopping");
    loadHistory();
    showToast(`Deleted “${title || "shopping session"}”.`);
  };

  const newSearch = () => {
    resetResults();
    navigate("/shopping");
  };

  // currency follows the result set (USD search → $ filters, not ₹)
  const activeCurrency = useMemo(
    () => products.find((p) => p.currency)?.currency || "INR",
    [products]
  );

  const priceBounds = useMemo(() => {    if (products.length === 0) return { min: 0, max: 100000 };
    const vals = products.map((p) => p.price).filter((v) => typeof v === "number" && v > 0);
    if (vals.length === 0) return { min: 0, max: 100000 };
    return { min: Math.floor(Math.min(...vals)), max: Math.ceil(Math.max(...vals)) };
  }, [products]);

  const filteredProducts = useMemo(() => {
    let res = [...products];

    if (filters.brands && filters.brands.length > 0) {
      res = res.filter((p) => filters.brands.includes(deriveBrandForFilter(p)));
    }
    if (filters.stores && filters.stores.length > 0) {
      res = res.filter((p) => filters.stores.includes((p.store || "").trim() || "Unknown"));
    }

    const allCurrencies = new Set(products.map((p) => p.currency).filter(Boolean));
    const mixed = allCurrencies.size > 1;
    if (!mixed) {
      if (filters.minPrice != null) {
        res = res.filter((p) => typeof p.price === "number" && p.price >= filters.minPrice);
      }
      if (filters.maxPrice != null) {
        res = res.filter((p) => typeof p.price === "number" && p.price <= filters.maxPrice);
      }
    }

    if (filters.minRating && filters.minRating !== "any") {
      const thr = parseFloat(filters.minRating);
      res = res.filter((p) => typeof p.rating === "number" && p.rating >= thr);
    }

    switch (filters.sortBy) {
      case "price_asc":
        res.sort((a, b) => a.price - b.price);
        break;
      case "price_desc":
        res.sort((a, b) => b.price - a.price);
        break;
      case "rating_desc":
        res.sort((a, b) => (b.rating ?? -1) - (a.rating ?? -1));
        break;
      default:
        break;
    }
    return res;
  }, [products, filters]);

  return (
    <div className="app qshop">
      <header className="sh-top">
      <Link to="/home" className="sh-top-btn" title="Dashboard" aria-label="Dashboard">
        <LayoutGrid size={18} />
        </Link>
        <div className="sh-title">
          <h1>{sessionId ? sessionTitle || "Shopping" : "Shopping"}</h1>
          <span className="sh-meta">
            Google Shopping + Amazon · {locationLabel(location)}
            {loading ? " · searching…" : lastSearched ? ` · last searched ${timeAgo(lastSearched)}` : ""}
          </span>
        </div>
        <button className="sh-top-btn" onClick={newSearch} title="New search" aria-label="New search">
          <Plus size={18} />
        </button>
      </header>

      <main className="app-main">
        {routerPrefill && <RouteReceipt prefill={routerPrefill} />}
    <ShoppingSearch
      onSearch={handleSearch}
      loading={loading}
      initialQuery={prefillQuery}
      locations={LOCATIONS}
          location={location}
          onLocationChange={changeLocation}
          locationLabel={locationLabel(location)}
          autoRun={!!routerPrefill?.autoRun}
        />
        <SearchProgress loading={loading} locationLabel={locationLabel(location)} />

        {sessionId && (
          <div className="session-head">
            <div>
              <h2>{sessionTitle || "Saved shopping"}</h2>
              {lastSearched && (
                <p className="sess-sub">
                  {sessionLocation ? `${locationLabel(sessionLocation)} · ` : ""}Last searched {timeAgo(lastSearched)} · prices may have changed
                </p>
              )}
            </div>
            <div className="session-actions">
              <button className="btn-again" disabled={loading} onClick={() => handleSearch(sessionTitle, { again: true })}>
                ↻ Search again
              </button>
              <button className="btn-ghost" onClick={newSearch}>+ New search</button>
            </div>
          </div>
        )}

        {partial && (
          <div className="sh-partial" role="note">
            <span>⚠ This saved result is partial — kept {partial.saved} of {partial.total} products (older version).</span>
            <button className="btn-again" disabled={loading} onClick={() => handleSearch(sessionTitle, { again: true })}>
              Search again for the full list
            </button>
          </div>
        )}

        {error && <EmptyState error={error} />}
        {followUp && <EmptyState followUp={followUp} />}

        {!loading && !error && !followUp && hasSearched && products.length === 0 && <EmptyState />}

        {!loading && products.length > 0 && (
          <div className="results-container">
            <div className="results-sidebar">
              <ShoppingFilters
                products={products}
                filters={filters}
                onFilterChange={setFilters}
                priceBounds={priceBounds}
                currencySymbol={currencySymbol(activeCurrency)}
                numberLocale={currencyLocale(activeCurrency)}
              />
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
                <div className="no-results premium">
                  <SlidersHorizontal size={16} /> No products match your filters. Clear or adjust price/rating.
                </div>
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
          <>
            <div className="hero-empty">
              <h2>Find your next favourite product</h2>
              <p>Search live Google Shopping + Amazon results. Filter by brand, store, price &amp; rating — instantly.</p>
            </div>
            <div className="recent-wrap">
              <div className="recent-head">
                <span className="recent-ico"><History size={15} /></span>
                <h3>Recent Shopping</h3>
                {sessions.length > 0 && <span className="recent-count">{sessions.length}</span>}
                {sessions.length > 0 && <span className="recent-hint">Opens saved results · no new search spent</span>}
              </div>
              {sessions.length === 0 ? (
                <div className="recent-empty">No shopping history yet — your searches will appear here.</div>
              ) : (
                <div className="recent-grid">
                  {sessions.map((s) => (
                    <div key={s.session_id} className="recent-card">
                      <button className="open" onClick={() => navigate(`/shopping/${s.session_id}`)}>
                        <strong>{s.title}</strong>
                        <span className="rc-srcs">
                          {(s.sources || []).includes("amazon") && <span className="rc-src amazon">Amazon</span>}
                          {(s.sources || []).includes("google_shopping") && <span className="rc-src google">Google Shopping</span>}
                        </span>
                      </button>
                      <div className="rc-foot">
                        <span>
                          <span className="rc-count">{s.product_count ?? 0} products</span>
                          <span className="rc-time">· {timeAgo(s.last_search_at || s.updated_at)}{s.location ? ` · ${s.location_label || s.location}` : ""}</span>
                        </span>
                        <button className="rc-del" title="Delete" aria-label="Delete session" onClick={() => setConfirmDelete(s)}>
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </main>

      {confirmDelete && (
        <div className="sh-modal-wrap" onClick={() => setConfirmDelete(null)}>
          <div className="sh-modal" onClick={(e) => e.stopPropagation()}>
            <h4>Delete this shopping session?</h4>
            <p className="sh-modal-q">“{confirmDelete.title}”</p>
            <p>Its saved results will be removed permanently.</p>
            <div className="sh-modal-actions" style={{ marginTop: 14 }}>
              <button className="btn-ghost" onClick={() => setConfirmDelete(null)}>Cancel</button>
              <button
                className="btn-danger"
                onClick={() => {
                  const { session_id, title } = confirmDelete;
                  setConfirmDelete(null);
                  removeSession(session_id, title);
                }}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {toast && <div className="sh-toast" role="status">{toast}</div>}
    </div>
  );
}
