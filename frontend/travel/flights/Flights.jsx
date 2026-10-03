import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { SlidersHorizontal, History, Trash2, LayoutGrid, Plus, Building2, Route } from "lucide-react";
import FlightSearch from "./components/FlightSearch";
import FlightCard from "./components/FlightCard";
import FlightDetails from "./components/FlightDetails";
import FlightFilters from "./components/FlightFilters";
import { PriceDisclaimer, GuideButton } from "../../src/shared/TravelGuide";
import { flightsApi, timeAgo } from "./api";
import { useRouterPrefill } from "../../src/shared/useRouterPrefill";
import { getToken } from "../../auth/api";
// Styles shared with the hotels and trips pages. Flights.css is gone: it had no
// rules of its own, every one of them lived in the other two stylesheets too.
import "../shared/travel.css";

const DEFAULT_FILTERS = { stops: "any", airlines: [], maxPrice: null, sortBy: "price_asc" };

export default function Flights() {
  const navigate = useNavigate();
  const { sessionId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();

  const [flights, setFlights] = useState([]);
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
  const [flightParams, setFlightParams] = useState(null);
  // Question handed over from the dashboard; fills the form only.
  const [prefillQuery, setPrefillQuery] = useState("");
  const [prefillFields, setPrefillFields] = useState(null);
  const routerPrefill = useRouterPrefill("flights");

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
      const data = await flightsApi.history(20);
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
    setFlights([]);
    setError(null);
    setFollowUp(null);
    setHasSearched(false);
    setFilters({ ...DEFAULT_FILTERS });
    setSessionTitle("");
    setSelected(null);
    setFlightParams(null);
    setLastSearched("");
  };

  const handleSearch = async (query, opts = {}) => {
    const q = (query || "").trim();
    if (!q || loading) return;
    setLoading(true);
    setError(null);
    setFollowUp(null);
    setSelected(null);
    setFlights([]);
    setHasSearched(true);
    setFilters({ ...DEFAULT_FILTERS });
    try {
      const result = opts.again
        ? await flightsApi.searchAgain(sessionId, q)
        : await flightsApi.search({ query: q, session_id: sessionId || undefined });
      setFlights(result.flights || []);
      setFlightParams(result.params || null);
      setSessionTitle(q);
      setLastSearched(new Date().toISOString());
      if (result.session_id && result.session_id !== sessionId) {
        navigate(`/flights/${result.session_id}`, { replace: !sessionId });
      }
      loadHistory();
    } catch (err) {
      if (err.code === "unauthorized") {
        navigate("/login", { replace: true });
        return;
      }
      if (err.code === 422) setFollowUp(err.message);
      else setError(err.message || "Flight search is temporarily unavailable. Please try again.");
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
    flightsApi
      .getSession(sessionId)
      .then((d) => {
        if (!alive) return;
        const latest = d.latest;
        setSessionTitle(d.session?.title || d.session?.query || "");
        setLastSearched(d.session?.last_search_at || latest?.created_at || "");
        setFlights(latest?.flights || []);
        setFlightParams(latest?.params || d.session?.params || null);
        setHasSearched(true);
      })
      .catch((e) => {
        if (!alive) return;
        if (e.code === "unauthorized") navigate("/login", { replace: true });
        else setError(e.message || "Could not load this flight session.");
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
    setFlights([]);
    setHasSearched(false);
    setError(null);
    setFollowUp(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, sessionId]);

  const removeSession = async (id, title) => {
    try {
      await flightsApi.remove(id);
    } catch {
      showToast("Could not delete this session.");
      return;
    }
    if (id === sessionId) navigate("/flights");
    loadHistory();
    showToast(`Deleted “${title || "flight session"}”.`);
  };

  const newSearch = () => {
    resetResults();
    navigate("/flights");
  };

  const priceBounds = useMemo(() => {
    if (flights.length === 0) return { min: 0, max: 2000 };
    const vals = flights.map((f) => f.price).filter((v) => typeof v === "number" && v > 0);
    if (vals.length === 0) return { min: 0, max: 2000 };
    return { min: Math.floor(Math.min(...vals)), max: Math.ceil(Math.max(...vals)) };
  }, [flights]);

  // Cheapest / fastest across the full result set (Google-style highlights).
  const highlights = useMemo(() => {
    const priced = flights.filter((f) => typeof f.price === "number" && f.price > 0);
    const timed = flights.filter((f) => typeof f.duration === "number" && f.duration > 0);
    const out = {};
    if (priced.length > 0) {
      const cheapest = priced.reduce((a, b) => (a.price <= b.price ? a : b));
      out[cheapest.id] = { ...(out[cheapest.id] || {}), cheapest: true };
    }
    if (timed.length > 0) {
      const fastest = timed.reduce((a, b) => (a.duration <= b.duration ? a : b));
      out[fastest.id] = { ...(out[fastest.id] || {}), fastest: true };
    }
    return out;
  }, [flights]);

  const filteredFlights = useMemo(() => {
    let res = [...flights];
    if (filters.stops && filters.stops !== "any") {
      if (filters.stops === "2+") res = res.filter((f) => (f.stops ?? 0) >= 2);
      else res = res.filter((f) => (f.stops ?? 0) === parseInt(filters.stops));
    }
    if (filters.airlines && filters.airlines.length > 0) {
      res = res.filter((f) => filters.airlines.includes(f.airline));
    }
    if (filters.maxPrice != null) {
      res = res.filter((f) => typeof f.price === "number" && f.price <= filters.maxPrice);
    }
    switch (filters.sortBy) {
      case "price_desc": res.sort((a, b) => b.price - a.price); break;
      case "duration": res.sort((a, b) => (a.duration ?? 0) - (b.duration ?? 0)); break;
      default: res.sort((a, b) => a.price - b.price);
    }
    return res;
  }, [flights, filters]);

  return (
    <div className="app qshop">
      <header className="sh-top">
      <Link to="/home" className="sh-top-btn" title="Dashboard" aria-label="Dashboard">
        <LayoutGrid size={18} />
        </Link>
        <div className="sh-title">
          <h1>{sessionId ? sessionTitle || "Flights" : "Flights"}</h1>
          <span className="sh-meta">
            Google Flights{loading ? " · searching…" : lastSearched ? ` · last searched ${timeAgo(lastSearched)}` : ""}
          </span>
        </div>
        <Link to="/hotels" className="sh-top-btn" title="Hotels" aria-label="Hotels">
          <Building2 size={18} />
        </Link>
        <Link to="/trips" className="sh-top-btn" title="Trips" aria-label="Trips">
          <Route size={18} />
        </Link>
        <GuideButton kind="flights" />
        <button className="sh-top-btn" onClick={newSearch} title="New search" aria-label="New search">
          <Plus size={18} />
        </button>
      </header>

      <main className="app-main">
        <PriceDisclaimer />
        <FlightSearch onSearch={handleSearch} loading={loading} initialQuery={prefillQuery} initialFields={prefillFields} autoRun={!!routerPrefill?.autoRun} />
        {loading && <p className="search-hint"><span className="dot-pulse" /> Searching live flights…</p>}

        {sessionId && (
          <div className="session-head">
            <div>
              <h2>{sessionTitle || "Saved flights"}</h2>
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
        {!loading && !error && !followUp && hasSearched && flights.length === 0 && (
          <div className="no-results premium">No flights found. Try nearby airports or different dates.</div>
        )}

        {!loading && flights.length > 0 && (
          <div className="results-container">
            <div className="results-sidebar">
              <div className="filter-panel">
                <div className="filter-head">
                  <span>Sort:</span>
                  <select value={filters.sortBy} onChange={(e) => setFilters({ ...filters, sortBy: e.target.value })} className="toolbar-select">
                    <option value="price_asc">Price: Low → High</option>
                    <option value="price_desc">Price: High → Low</option>
                    <option value="duration">Fastest</option>
                  </select>
                </div>
                <FlightFilters flights={flights} filters={filters} onFilterChange={setFilters} priceBounds={priceBounds} />
              </div>
            </div>
            <div className="results-main">
              <div className="results-toolbar">
                <div className="results-count">
                  <span className="count-strong">{filteredFlights.length}</span> of {flights.length} flights
                </div>
              </div>
              {filteredFlights.length === 0 ? (
                <div className="no-results premium">
                  <SlidersHorizontal size={16} /> No flights match your filters.
                </div>
              ) : (
                <div className="shopping-grid">
                  {filteredFlights.map((f) => (
                    <FlightCard key={f.id} flight={f} onSelect={setSelected} highlight={highlights[f.id]} />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {!hasSearched && !loading && (
          <>
            <div className="hero-empty">
              <h2>Find your next flight</h2>
              <p>Live Google Flights results. Filter by stops, airline &amp; price.</p>
            </div>
            <div className="recent-wrap">
              <div className="recent-head">
                <span className="recent-ico"><History size={15} /></span>
                <h3>Recent Flights</h3>
                {sessions.length > 0 && <span className="recent-count">{sessions.length}</span>}
                {sessions.length > 0 && <span className="recent-hint">Opens saved results · no new search spent</span>}
              </div>
              {sessions.length === 0 ? (
                <div className="recent-empty">No flight history yet — your searches will appear here.</div>
              ) : (
                <div className="recent-grid">
                  {sessions.map((s) => (
                    <div key={s.session_id} className="recent-card">
                      <button className="open" onClick={() => navigate(`/flights/${s.session_id}`)}>
                        <strong>{s.title}</strong>
                      </button>
                      <div className="rc-foot">
                        <span>
                          <span className="rc-count">{s.flight_count ?? 0} flights</span>
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
            <h4>Delete this flight session?</h4>
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
        <FlightDetails flight={selected} searchContext={flightParams} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}
