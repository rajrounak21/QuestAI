import { useEffect, useRef, useState } from "react";
import { Search, ArrowRight, Sparkles, MapPin } from "lucide-react";
import { CURRENCIES } from "../../../src/shared/api";

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

export default function TripSearch({ onSearch, loading, initialValues, actions, autoRun = false }) {
  const iv = initialValues || {};
  const [origin, setOrigin] = useState(iv.origin || "");
  const [destination, setDestination] = useState(iv.destination || "");
  const [departureDate, setDepartureDate] = useState(iv.departure_date || "");
  const [duration, setDuration] = useState(iv.duration_days || 5);
  const [travelers, setTravelers] = useState(iv.travelers || 2);
  const [budget, setBudget] = useState(
    iv.budget?.max_total != null ? String(iv.budget.max_total) : ""
  );
  // Set by the router: an explicit symbol wins, otherwise it is derived from the
  // origin city. Default INR matches the shopping location default. Either way it
  // is visible in the dropdown, never inferred silently from the number.
  const [currency, setCurrency] = useState(
    iv.budget?.currency || iv.budget_currency || "INR"
  );
  const autoRunRef = useRef(false);

  const valid = origin.trim() && destination.trim() && departureDate && Number(budget) >= 100;

  // initialValues is also read into state on mount, but a question handed over
  // from the dashboard (/trips?q=...) arrives after mount, so re-apply whenever
  // it changes.
  useEffect(() => {
    if (!iv.origin && !iv.destination && !iv.departure_date) return;
    if (iv.origin) setOrigin(iv.origin);
    if (iv.destination) setDestination(iv.destination);
    if (iv.departure_date) setDepartureDate(iv.departure_date);
    if (iv.duration_days) setDuration(iv.duration_days);
    if (iv.travelers) setTravelers(iv.travelers);
    if (iv.budget?.max_total != null) setBudget(String(iv.budget.max_total));
    if (iv.budget?.currency) setCurrency(iv.budget.currency);
    if (iv.budget_currency) setCurrency(iv.budget_currency);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialValues]);

  const buildQuery = () => {
    // Structured form -> single NL string for the LLM extract node. The currency
    // is stated explicitly: it used to append the literal word "dollars", so a
    // rupee budget was read as a dollar budget downstream.
    return (
      `${duration}-day trip from ${origin.trim()} to ${destination.trim()} ` +
      `departing ${departureDate} for ${travelers} people, budget ${Number(budget)} ${currency}`
    );
  };

  const handleSubmit = (e, actionId) => {
    e.preventDefault();
    if (!valid || loading) return;
    onSearch(buildQuery(), actionId);
  };

  // The trip planner is the most expensive run in the app, so autoRun only fires
  // on the same `valid` the Search button requires - a real date and a real
  // budget. Anything less and the user decides. Declared last so it observes
  // state the two effects above have already settled.
  useEffect(() => {
    if (!autoRun || autoRunRef.current || loading) return;
    if (!valid) return;
    autoRunRef.current = true;
    onSearch(buildQuery());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRun, valid, loading, origin, destination, departureDate, duration, travelers, budget, currency]);

  return (
    <div className="search-hero">
      <form className="fl-form" onSubmit={handleSubmit}>
        <div className="fl-grid">
          <label className="fl-field">
            <span><MapPin size={13} /> From</span>
            <input type="text" value={origin} onChange={(e) => setOrigin(e.target.value)}
              placeholder="City (e.g. Delhi)" className="fl-input" disabled={loading} required />
          </label>
          <label className="fl-field">
            <span><MapPin size={13} /> To</span>
            <input type="text" value={destination} onChange={(e) => setDestination(e.target.value)}
              placeholder="City (e.g. Dubai)" className="fl-input" disabled={loading} required />
          </label>
          <label className="fl-field">
            <span>Departure</span>
            <input type="date" value={departureDate} min={todayISO()}
              onChange={(e) => setDepartureDate(e.target.value)} className="fl-input" disabled={loading} required />
          </label>
          <label className="fl-field">
            <span>Days</span>
            <input type="number" min={1} max={30} value={duration}
              onChange={(e) => setDuration(parseInt(e.target.value) || 5)} className="fl-input" disabled={loading} />
          </label>
          <label className="fl-field">
            <span>Travelers</span>
            <input type="number" min={1} max={20} value={travelers}
              onChange={(e) => setTravelers(parseInt(e.target.value) || 2)} className="fl-input" disabled={loading} />
          </label>
          <label className="fl-field">
            <span>Budget</span>
            <span className="input-with-symbol">
              {/* An explicit symbol in the query wins, then the origin city.
                  Never guessed from the number itself - "40000" means nothing
                  without a currency, and assuming one silently inflated it 83x. */}
              <select value={currency} onChange={(e) => setCurrency(e.target.value)} className="fl-input" disabled={loading} aria-label="Budget currency">
                {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
              <input type="number" min={100} value={budget}
                onChange={(e) => setBudget(e.target.value)} placeholder="e.g. 2500"
                className="fl-input" disabled={loading} required />
            </span>
          </label>
        </div>
        <div className="search-row">
          {actions && actions.length > 0 ? (
            actions.map((a) => (
              <button
                key={a.id}
                type="button"
                disabled={loading || !valid}
                className={a.primary === false ? "btn-ghost" : "search-btn"}
                onClick={(e) => handleSubmit(e, a.id)}
              >
                {loading ? (
                  <span className="btn-loading"><span className="spinner-small" /> Planning</span>
                ) : (
                  a.label
                )}
              </button>
            ))
          ) : (
            <button type="button" disabled={loading || !valid} className="search-btn" onClick={(e) => handleSubmit(e, undefined)}>
              {loading ? (
                <span className="btn-loading"><span className="spinner-small" /> Planning</span>
              ) : (
                <><Search size={16} /> Plan Trip <ArrowRight size={16} /></>
              )}
            </button>
          )}
        </div>
        {!actions && (
          <>
            <div className="search-suggestions">
              <span className="sugg-label"><Sparkles size={12} /> Try:</span>
              {["Delhi to Dubai", "Mumbai to Bali", "Bengaluru to Singapore"].map((s) => (
                <button
                  key={s}
                  type="button"
                  className="sugg-chip"
                  disabled={loading}
                  onClick={() => {
                    const m = s.match(/(.+?)\s+to\s+(.+)/i);
                    if (m) {
                      setOrigin(m[1].trim());
                      setDestination(m[2].trim());
                    }
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
            <p className="search-hint"><span className="dot-pulse" /> Flights + hotels + day-by-day itinerary, planned together</p>
          </>
        )}
      </form>
    </div>
  );
}
