import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { SlidersHorizontal, History, Trash2, LayoutGrid, Plus, Plane, Route } from "lucide-react";
import HotelSearch from "./components/HotelSearch";
import HotelCard from "./components/HotelCard";
import HotelDetails from "./components/HotelDetails";
import HotelFilters from "./components/HotelFilters";
import { PriceDisclaimer, GuideButton } from "../../src/shared/TravelGuide";
import { hotelsApi, timeAgo } from "./api";
import { useRouterPrefill } from "../../src/shared/useRouterPrefill";
import RouteReceipt from "../../src/shared/RouteReceipt";
import { getToken } from "../../auth/api";
import "./Hotels.css";
// Styles shared with the flights and trips pages. Used to be a copy-paste of
// this same block in all three stylesheets.
import "../shared/travel.css";

const DEFAULT_FILTERS = { minRating: "any", amenities: [], maxPrice: null, freeCancellation: false, sortBy: "relevance" };

export default function Hotels() {
  const navigate = useNavigate();
  const { sessionId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();

  const [hotels, setHotels] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [followUp, setFollowUp] = useState(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [filters, setFilters] = useState({ ...DEFAULT_FILTERS });

  const [sessions, setSessions] = useState([]);
  const [sessionTitle, setSessionTitle] = useState("");
  const [lastSearched, setLastSearched] = useState("");

  const [confirmDelete, setConfirmDelete] = useState(null);
  const [toast, setToast] = useState("");
  const [selected, setSelected] = useState(null);
  // Question handed over from the dashboard; fills the form only.
  const [prefillQuery, setPrefillQuery] = useState("");
  const [prefillFields, setPrefillFields] = useState(null);
  const routerPrefill = useRouterPrefill("hotels");

  const autoRunRef = useRef(false);
  const toastTimer = useRef(null);

  const showToast = (msg) => {
    setToast(msg);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(""), 3000);
  };

  useEffect(() => () => { if (toastTimer.current) clearTimeout(toastTimer.current); }, []);

  const loadHistory = async () => {
    try {
      const data = await hotelsApi.history(20);
      setSessions(data.items || []);
    } catch { /* history stays empty */ }
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
    setHotels([]);
    setError(null);
    setFollowUp(null);
    setHasSearched(false);
    setFilters({ ...DEFAULT_FILTERS });
    setSessionTitle("");
    setSelected(null);
    setLastSearched("");
  };

  const handleSearch = async (query, opts = {}) => {
    const q = (query || "").trim();
    if (!q || loading) return;
    setLoading(true);
    setError(null);
    setFollowUp(null);
    setSelected(null);
    setHotels([]);
    setHasSearched(true);
    setFilters({ ...DEFAULT_FILTERS });
    try {
      const result = opts.again
        ? await hotelsApi.searchAgain(sessionId, q)
        : await hotelsApi.search({ query: q, session_id: sessionId || undefined });
      setHotels(result.hotels || []);
      setSessionTitle(q);
      setLastSearched(new Date().toISOString());
      if (result.session_id && result.session_id !== sessionId) {
        navigate(`/hotels/${result.session_id}`, { replace: !sessionId });
      }
      loadHistory();
    } catch (err) {
      if (err.code === "unauthorized") {
        navigate("/login", { replace: true });
        return;
      }
      if (err.code === 422) setFollowUp(err.message);
      else setError(err.message || "Hotel search is temporarily unavailable. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // Open saved session from Mongo (zero SerpApi cost)
  useEffect(() => {
    if (!sessionId) {
      resetResults();
      return;
    }
    let alive = true;
    setLoading(true);
    hotelsApi
      .getSession(sessionId)
      .then((d) => {
        if (!alive) return;
        const latest = d.latest;
        setSessionTitle(d.session?.title || d.session?.query || "");
        setLastSearched(d.session?.last_search_at || latest?.created_at || "");
        setHotels(latest?.hotels || []);
        setHasSearched(true);
      })
      .catch((e) => {
        if (!alive) return;
        if (e.code === "unauthorized") navigate("/login", { replace: true });
        else setError(e.message || "Could not load this hotel session.");
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => { alive = false; };
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
    setPrefillQuery(q);
    setPrefillFields(routerPrefill?.fields || null);
    setHotels([]);
    setHasSearched(false);
    setError(null);
    setFollowUp(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, sessionId]);

  const removeSession = async (id, title) => {
    try {
      await hotelsApi.remove(id);
    } catch {
      showToast("Could not delete this session.");
      return;
    }
    if (id === sessionId) navigate("/hotels");
    loadHistory();
    showToast(`Deleted “${title || "hotel session"}”.`);
  };

  const newSearch = () => {
    resetResults();
    navigate("/hotels");
  };

  const priceBounds = useMemo(() => {
    if (hotels.length === 0) return { min: 0, max: 1000 };
    const vals = hotels.map((h) => h.price_per_night).filter((v) => typeof v === "number" && v > 0);
    if (vals.length === 0) return { min: 0, max: 1000 };
    return { min: Math.floor(Math.min(...vals)), max: Math.ceil(Math.max(...vals)) };
  }, [hotels]);

  const filteredHotels = useMemo(() => {
    let res = [...hotels];
    if (filters.minRating && filters.minRating !== "any") {
      const thr = parseFloat(filters.minRating);
      res = res.filter((h) => typeof h.rating === "number" && h.rating >= thr);
    }
    if (filters.maxPrice != null) {
      res = res.filter((h) => typeof h.price_per_night === "number" && h.price_per_night <= filters.maxPrice);
    }
    if (filters.amenities && filters.amenities.length > 0) {
      res = res.filter((h) => filters.amenities.every((a) => (h.amenities || []).includes(a)));
    }
    if (filters.freeCancellation) {
      res = res.filter((h) => h.free_cancellation);
    }
    switch (filters.sortBy) {
      case "price_asc": res.sort((a, b) => (a.price_per_night || 0) - (b.price_per_night || 0)); break;
      case "price_desc": res.sort((a, b) => (b.price_per_night || 0) - (a.price_per_night || 0)); break;
      case "rating_desc": res.sort((a, b) => (b.rating ?? -1) - (a.rating ?? -1)); break;
      default: break;
    }
    return res;
  }, [hotels, filters]);

  return (
    <div className="app qshop">
      <header className="sh-top">
      <Link to="/home" className="sh-top-btn" title="Dashboard" aria-label="Dashboard">
        <LayoutGrid size={18} />
        </Link>
        <div className="sh-title">
          <h1>{sessionId ? sessionTitle || "Hotels" : "Hotels"}</h1>
          <span className="sh-meta">
            Google Hotels{loading ? " · searching…" : lastSearched ? ` · last searched ${timeAgo(lastSearched)}` : ""}
          </span>
        </div>
        <Link to="/flights" className="sh-top-btn" title="Flights" aria-label="Flights">
          <Plane size={18} />
        </Link>
        <Link to="/trips" className="sh-top-btn" title="Trips" aria-label="Trips">
          <Route size={18} />
        </Link>
        <GuideButton kind="hotels" />
        <button className="sh-top-btn" onClick={newSearch} title="New search" aria-label="New search">
          <Plus size={18} />
        </button>
      </header>

      <main className="app-main">
        <PriceDisclaimer />
        {routerPrefill && <RouteReceipt prefill={routerPrefill} />}
        <HotelSearch onSearch={handleSearch} loading={loading} initialQuery={prefillQuery} initialFields={prefillFields} autoRun={!!routerPrefill?.autoRun} />
        {loading && <p className="search-hint"><span className="dot-pulse" /> Searching live hotels…</p>}

        {sessionId && (
          <div className="session-head">
            <div>
              <h2>{sessionTitle || "Saved hotels"}</h2>
              {lastSearched && <p className="sess-sub">Last searched {timeAgo(lastSearched)} · prices may have changed</p>}
            </div>
            <div className="session-actions">
              <button className="btn-again" disabled={loading} onClick={() => handleSearch(sessionTitle, { again: true })}>
                ↻ Search again
              </button>
              <button className="btn-ghost" onClick={newSearch}>+ New search</button>
            </div>
          </div>
        )}

        {error && <div className="no-results premium">{error}</div>}
        {followUp && <div className="no-results premium">Need more detail: {followUp}</div>}
        {!loading && !error && !followUp && hasSearched && hotels.length === 0 && (
          <div className="no-results premium">No hotels found. Try a nearby city or different dates.</div>
        )}

        {!loading && hotels.length > 0 && (
          <div className="results-container">
            <div className="results-sidebar">
              <div className="filter-panel">
                <div className="filter-head">
                  <span>Sort:</span>
                  <select value={filters.sortBy} onChange={(e) => setFilters({ ...filters, sortBy: e.target.value })} className="toolbar-select">
                    <option value="relevance">Recommended</option>
                    <option value="price_asc">Price: Low → High</option>
                    <option value="price_desc">Price: High → Low</option>
                    <option value="rating_desc">Top Rated</option>
                  </select>
                </div>
                <HotelFilters hotels={hotels} filters={filters} onFilterChange={setFilters} priceBounds={priceBounds} />
              </div>
            </div>
            <div className="results-main">
              <div className="results-toolbar">
                <div className="results-count">
                  <span className="count-strong">{filteredHotels.length}</span> of {hotels.length} hotels
                </div>
              </div>
              {filteredHotels.length === 0 ? (
                <div className="no-results premium">
                  <SlidersHorizontal size={16} /> No hotels match your filters.
                </div>
              ) : (
                <div className="shopping-grid">
                  {filteredHotels.map((h) => (
                    <HotelCard key={h.id} hotel={h} onSelect={setSelected} />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {!hasSearched && !loading && (
          <>
            <div className="hero-empty">
              <h2>Find your next stay</h2>
              <p>Live Google Hotels results. Filter by rating, price, amenities &amp; free cancellation.</p>
            </div>
            <div className="recent-wrap">
              <div className="recent-head">
                <span className="recent-ico"><History size={15} /></span>
                <h3>Recent Hotels</h3>
                {sessions.length > 0 && <span className="recent-count">{sessions.length}</span>}
                {sessions.length > 0 && <span className="recent-hint">Opens saved results · no new search spent</span>}
              </div>
              {sessions.length === 0 ? (
                <div className="recent-empty">No hotel history yet — your searches will appear here.</div>
              ) : (
                <div className="recent-grid">
                  {sessions.map((s) => (
                    <div key={s.session_id} className="recent-card">
                      <button className="open" onClick={() => navigate(`/hotels/${s.session_id}`)}>
                        <strong>{s.title}</strong>
                      </button>
                      <div className="rc-foot">
                        <span>
                          <span className="rc-count">{s.hotel_count ?? 0} hotels</span>
                          <span className="rc-time">· {timeAgo(s.last_search_at || s.updated_at)}</span>
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
            <h4>Delete this hotel session?</h4>
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

      {selected && (
        <HotelDetails hotel={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}
