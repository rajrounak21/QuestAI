import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { History, Trash2, LayoutGrid, Plus, Plane, Building2 } from "lucide-react";
import TripSearch from "./components/TripSearch";
import TripThread from "./components/TripThread";
import Collapsible from "./components/Collapsible";
import TripOverview from "./components/TripOverview";
import TripItinerary from "./components/TripItinerary";
import FlightCard from "../flights/components/FlightCard";
import FlightDetails from "../flights/components/FlightDetails";
import HotelCard from "../hotels/components/HotelCard";
import HotelDetails from "../hotels/components/HotelDetails";
import { tripsApi, timeAgo } from "./api";
import { parseTripQuery } from "../shared/parseQuery";
import { useRouterPrefill } from "../../src/shared/useRouterPrefill";
import { mergeFields } from "../../src/shared/mergeFields";
import { getToken } from "../../auth/api";
import ErrorBoundary from "../../src/shared/ErrorBoundary";
import { PriceDisclaimer, GuideButton } from "../../src/shared/TravelGuide";
import "./Trips.css";
// Styles shared with the flights and hotels pages. Used to be a copy-paste of
// this same block in all three stylesheets.
import "../shared/travel.css";

const POLL_MS = 2500;
const POLL_MAX_TRIES = 200; // ~8 min ceiling, trips run 1-3 min
const TERMINAL = ["ready", "awaiting_input", "failed"];

export default function Trips() {
  const navigate = useNavigate();
  const { sessionId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();

  const [doc, setDoc] = useState(null);
  const [running, setRunning] = useState(false);
  const [stale, setStale] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [sessions, setSessions] = useState([]);
  const [lastSearched, setLastSearched] = useState("");

  const [selectedFlight, setSelectedFlight] = useState(null);
  const [selectedHotel, setSelectedHotel] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [toast, setToast] = useState("");
  const [notice, setNotice] = useState("");
  const [loadingSession, setLoadingSession] = useState(false);

  // Question handed over from the dashboard; fills the form only.
  const [prefillValues, setPrefillValues] = useState(null);
  const routerPrefill = useRouterPrefill("trips");

  const autoRunRef = useRef(false);
  const pollRef = useRef(null);
  const elapsedRef = useRef(null);
  const startedRef = useRef(null);
  const toastTimer = useRef(null);

  const showToast = (msg) => {
    setToast(msg);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(""), 3000);
  };

  useEffect(() => () => {
    stopPoll();
    if (toastTimer.current) clearTimeout(toastTimer.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadHistory = async () => {
    try {
      const data = await tripsApi.history(20);
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

  const stopPoll = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = null;
    if (elapsedRef.current) clearInterval(elapsedRef.current);
    elapsedRef.current = null;
  };

  const pollUntilDone = (id) => {
    stopPoll();
    setRunning(true);
    setStale(false);
    setNotice("");
    startedRef.current = Date.now();
    setElapsed(0);
    elapsedRef.current = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startedRef.current) / 1000));
    }, 1000);

    let tries = 0;
    let errs = 0;
    pollRef.current = setInterval(async () => {
      tries += 1;
      try {
        const d = await tripsApi.getSession(id);
        errs = 0;
        setDoc(d);
        setLastSearched(d.updated_at || "");
        if (TERMINAL.includes(d.status)) {
          stopPoll();
          setRunning(false);
          setStale(false);
          loadHistory();
        } else if (tries >= 8) {
          setStale(true); // alive but slow — trips take minutes
        }
        if (tries >= POLL_MAX_TRIES) {
          stopPoll();
          setRunning(false);
          loadHistory();
        }
      } catch (e) {
        if (e.code === "unauthorized") {
          stopPoll();
          setRunning(false);
          navigate("/login", { replace: true });
          return;
        }
        if (++errs >= 10) {
          stopPoll();
          setRunning(false);
          setNotice("Lost connection to the server. Restart the backend and refresh.");
        }
      }
    }, POLL_MS);
  };

  const startPlan = async (query, opts = {}) => {
    const q = (query || "").trim();
    if (!q || running) return;
    setNotice("");
    setSelectedFlight(null);
    setSelectedHotel(null);
    try {
      const res = await tripsApi.plan({ query: q, session_id: sessionId || undefined });
      if (res.session_id && res.session_id !== sessionId) {
        navigate(`/trips/${res.session_id}`, { replace: !sessionId });
      }
      pollUntilDone(res.session_id);
    } catch (err) {
      if (err.code === "unauthorized") {
        navigate("/login", { replace: true });
        return;
      }
      if (err.code === 409) {
        // Already running — attach to it.
        pollUntilDone(err.detail?.session_id || sessionId);
        return;
      }
      setNotice(err.message || "Could not start trip planning. Please try again.");
    }
  };

  const sendChat = async (message) => {
    const msg = (message || "").trim();
    if (!msg || running || !sessionId) return;
    setNotice("");
    try {
      await tripsApi.chat(sessionId, msg);
      pollUntilDone(sessionId);
    } catch (err) {
      if (err.code === "unauthorized") {
        navigate("/login", { replace: true });
        return;
      }
      if (err.code === 409) {
        pollUntilDone(sessionId);
        return;
      }
      setNotice(err.message || "Could not send. Please try again.");
    }
  };

  // Form-modal submit (confirm_details gate): create forks a linked new
  // session, overwrite replans in place with modal approval. No silent moves.
  const handleDetailsSubmit = async (query, actionId) => {
    const q = (query || "").trim();
    if (!q || running) return;
    setNotice("");
    setSelectedFlight(null);
    setSelectedHotel(null);
    try {
      if (actionId === "overwrite" && sessionId) {
        await tripsApi.plan({
          query: q, session_id: sessionId, confirmed_scope: "overwrite",
        });
        pollUntilDone(sessionId);
      } else {
        const res = await tripsApi.plan({ query: q, parent_session_id: sessionId || undefined });
        if (res.session_id && res.session_id !== sessionId) {
          navigate(`/trips/${res.session_id}`, { replace: !sessionId });
        }
        pollUntilDone(res.session_id);
      }
    } catch (err) {
      if (err.code === "unauthorized") {
        navigate("/login", { replace: true });
        return;
      }
      if (err.code === 409) {
        pollUntilDone(err.detail?.session_id || sessionId);
        return;
      }
      setNotice(err.message || "Could not start trip planning. Please try again.");
    }
  };

  // Open saved trip (Mongo only, zero provider cost); attach if still running.
  // loadingSession gives instant feedback so the page never looks dead blank.
  const loadSessionDoc = () => {
    if (!sessionId) return;
    setLoadingSession(true);
    setNotice("");
    let alive = true;
    tripsApi
      .getSession(sessionId)
      .then((d) => {
        if (!alive) return;
        setDoc(d);
        setLastSearched(d.updated_at || "");
        setLoadingSession(false);
        if (!TERMINAL.includes(d.status)) pollUntilDone(sessionId);
        loadHistory();
      })
      .catch((e) => {
        if (!alive) return;
        setLoadingSession(false);
        if (e.code === "unauthorized") navigate("/login", { replace: true });
        else setNotice(e.message || "Could not load this trip.");
      });
    return () => { alive = false; };
  };

  useEffect(() => {
    if (!sessionId) {
      stopPoll();
      setDoc(null);
      setRunning(false);
      setLoadingSession(false);
      return;
    }
    const cleanup = loadSessionDoc();
    return () => { if (cleanup) cleanup(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  // ?q= from the dashboard only PREFILLS the form. It used to call startPlan(q)
  // here, which kicked off a full trip plan — the most expensive run in the app —
  // the moment the page opened. Nothing runs until the user presses Search.
  useEffect(() => {
    const q = searchParams.get("q");
    if (!q || autoRunRef.current || sessionId) return;
    autoRunRef.current = true;
    setSearchParams({}, { replace: true });
    // Merged per field so a value the router dropped still comes from the parser.
    // Router wins where it has one. TripSearch reads budget as
    // { budget: { max_total } } while the router returns it flat, so reshape.
    const f = mergeFields(routerPrefill?.fields, parseTripQuery(q));
    if (f.budget_max != null) {
      f.budget = { ...(f.budget || {}), max_total: Number(f.budget_max) };
      delete f.budget_max;
    }
    setPrefillValues(f);
    setDoc(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, sessionId]);

  const removeSession = async (id, title) => {
    try {
      await tripsApi.remove(id);
    } catch {
      showToast("Could not delete this trip.");
      return;
    }
    if (id === sessionId) navigate("/trips");
    loadHistory();
    showToast(`Deleted “${title || "trip"}”.`);
  };

  const newTrip = () => {
    stopPoll();
    setDoc(null);
    setRunning(false);
    setLoadingSession(false);
    setSelectedFlight(null);
    setSelectedHotel(null);
    navigate("/trips");
  };

  // Pin a flight/hotel as the trip's pick — instant, budget re-estimates live.
  const handleSelect = async (kind, item) => {
    if (!sessionId || running || !item) return;
    try {
      const res = await tripsApi.select(sessionId, kind, item.id);
      const d = await tripsApi.getSession(sessionId);
      setDoc(d);
      if (kind === "flight") setSelectedFlight(null);
      else setSelectedHotel(null);
      const b = res.trip?.budget || {};
      const total = (b.flight_actual || 0) + (b.hotel_actual || 0) + (b.activities_estimated || 0);
      const sym = (b.currency || "USD") === "USD" ? "$" : (b.currency || "") + " ";
      showToast(
        `${kind === "flight" ? "Flight" : "Hotel"} updated · est. total ${sym}${Math.round(total).toLocaleString()}`
      );
      loadHistory();
    } catch (e) {
      if (e.code === "unauthorized") {
        navigate("/login", { replace: true });
        return;
      }
      showToast("Could not update selection.");
    }
  };

  const trip = doc?.trip || null;
  const status = doc?.status || null;

  const flightContext = useMemo(() => {
    if (!trip) return null;
    return {
      origin: trip.origin || "",
      destination: trip.destination || "",
      departure_date: trip.departure_date || "",
      ...(trip.return_date ? { return_date: trip.return_date } : {}),
      trip_type: trip.return_date ? "round_trip" : "one_way",
      travelers: trip.travelers || 1,
    };
  }, [trip]);

  const fmtElapsed = (s) => (s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`);

  // Trip embeds rendered inside the assistant bubble (standalone-style).
  const renderTripDetail = () => {
    if (!(status === "ready" && trip)) return null;
    return (
      <>
        <TripOverview trip={trip} />

        {(trip.flight_results || []).length > 0 && (
          <Collapsible
            title="Flights"
            meta={trip.selected_flight ? `· picked ${trip.selected_flight.airline} ${trip.selected_flight.flight_number}` : `· ${(trip.flight_results || []).length} options`}
            badge={<span className="count-strong">{(trip.flight_results || []).length}</span>}
          >
            <div className="shopping-grid">
              {(trip.flight_results || []).map((f) => (
                <FlightCard key={f.id} flight={f} onSelect={setSelectedFlight}
                  selected={trip.selected_flight?.id === f.id} />
              ))}
            </div>
          </Collapsible>
        )}

        {(trip.hotel_results || []).length > 0 && (
          <Collapsible
            title="Hotels"
            meta={trip.selected_hotel ? `· picked ${trip.selected_hotel.name}` : `· ${(trip.hotel_results || []).length} options`}
            badge={<span className="count-strong">{(trip.hotel_results || []).length}</span>}
          >
            <div className="shopping-grid">
              {(trip.hotel_results || []).map((h) => (
                <HotelCard key={h.id} hotel={h} onSelect={setSelectedHotel}
                  selected={trip.selected_hotel?.id === h.id} />
              ))}
            </div>
          </Collapsible>
        )}

        <TripItinerary days={trip.itinerary} currency={(trip.budget || {}).currency} />
      </>
    );
  };

  return (
    <ErrorBoundary
      key={sessionId || "new"}
      fallbackTitle="This trip couldn't be displayed."
      onReset={() => { setDoc(null); loadSessionDoc(); }}
    >
    <div className="app qshop">
      <header className="sh-top">
      <Link to="/home" className="sh-top-btn" title="Dashboard" aria-label="Dashboard">
        <LayoutGrid size={18} />
        </Link>
        <div className="sh-title">
          <h1>{sessionId ? doc?.title || "Trip" : "Trips"}</h1>
          <span className="sh-meta">
            Flights + hotels + itinerary
            {running ? ` · planning… ${fmtElapsed(elapsed)}` : lastSearched ? ` · updated ${timeAgo(lastSearched)}` : ""}
          </span>
        </div>
        <Link to="/flights" className="sh-top-btn" title="Flights" aria-label="Flights">
          <Plane size={18} />
        </Link>
        <Link to="/hotels" className="sh-top-btn" title="Hotels" aria-label="Hotels">
          <Building2 size={18} />
        </Link>
        <GuideButton kind="trips" />
        <button className="sh-top-btn" onClick={newTrip} title="New trip" aria-label="New trip">
          <Plus size={18} />
        </button>
      </header>

      <main className="app-main">
        <PriceDisclaimer />
        <TripSearch onSearch={startPlan} loading={running} initialValues={prefillValues} />

        {loadingSession && (
          <div className="trip-loading" role="status" aria-live="polite">
            <p><span className="spinner" /> Loading your trip…</p>
            <div className="trip-skeleton">
              <div className="sk-line sk-w80" />
              <div className="sk-line sk-w60" />
              <div className="sk-grid">
                <div className="sk-card" />
                <div className="sk-card" />
                <div className="sk-card" />
              </div>
            </div>
          </div>
        )}

        {notice && <div className="no-results premium">{notice}</div>}

        {running && (
          <div className="trip-progress">
            <p>
              <span className="dot-pulse" /> {doc?.progress?.detail || "Planning your trip…"} · {fmtElapsed(elapsed)}
            </p>
            {stale && <p className="ext-text">Taking longer than usual — still working (trips take a few minutes).</p>}
          </div>
        )}

        {sessionId && (
          <TripThread
            doc={doc}
            running={running}
            stale={stale}
            elapsedText={fmtElapsed(elapsed)}
            onSend={sendChat}
            onAnswerClarifying={sendChat}
            onRetry={() => startPlan(doc?.query || "")}
            onSubmitDetails={handleDetailsSubmit}
            renderTripDetail={renderTripDetail}
          />
        )}

        {!sessionId && !running && (
          <>
            <div className="hero-empty">
              <h2>Plan your next trip</h2>
              <p>Flights, hotels and a day-by-day itinerary — planned together, refined over chat.</p>
            </div>
            <div className="recent-wrap">
              <div className="recent-head">
                <span className="recent-ico"><History size={15} /></span>
                <h3>Recent Trips</h3>
                {sessions.length > 0 && <span className="recent-count">{sessions.length}</span>}
                {sessions.length > 0 && <span className="recent-hint">Opens saved trips · no new planning spent</span>}
              </div>
              {sessions.length === 0 ? (
                <div className="recent-empty">No trips yet — your plans will appear here.</div>
              ) : (
                <div className="recent-grid">
                  {sessions.map((s) => (
                    <div key={s.session_id} className="recent-card">
                      <button className="open" onClick={() => navigate(`/trips/${s.session_id}`)}>
                        <strong>{s.title}</strong>
                        <span className="rc-srcs">
                          <span className="rc-src google">{s.status || ""}</span>
                        </span>
                      </button>
                      <div className="rc-foot">
                        <span>
                          <span className="rc-count">{s.destination || ""}</span>
                          <span className="rc-time">· {timeAgo(s.updated_at)}</span>
                        </span>
                        <button className="rc-del" title="Delete" aria-label="Delete trip" onClick={() => setConfirmDelete(s)}>
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

      {selectedFlight && (
        <FlightDetails flight={selectedFlight} searchContext={flightContext} onClose={() => setSelectedFlight(null)}
          onSelect={(f) => handleSelect("flight", f)}
          isSelected={trip?.selected_flight?.id === selectedFlight.id} />
      )}
      {selectedHotel && (
        <HotelDetails hotel={selectedHotel} onClose={() => setSelectedHotel(null)}
          onSelect={(h) => handleSelect("hotel", h)}
          isSelected={trip?.selected_hotel?.id === selectedHotel.id} />
      )}

      {confirmDelete && (
        <div className="sh-modal-wrap" onClick={() => setConfirmDelete(null)}>
          <div className="sh-modal" onClick={(e) => e.stopPropagation()}>
            <h4>Delete this trip?</h4>
            <p className="sh-modal-q">“{confirmDelete.title}”</p>
            <p>Its saved plan will be removed permanently.</p>
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
    </ErrorBoundary>
  );
}
