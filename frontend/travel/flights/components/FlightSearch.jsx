import { useEffect, useRef, useState } from "react";
import { Search, ArrowRight, Sparkles, Plane } from "lucide-react";
import { parseFlightQuery } from "../../shared/parseQuery";
import { mergeFields } from "../../../src/shared/mergeFields";

const suggestions = [
  "Delhi to Dubai",
  "Mumbai to London",
  "Bengaluru to Singapore",
];

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

export default function FlightSearch({ onSearch, loading, initialQuery = "", initialFields = null, autoRun = false }) {
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [departureDate, setDepartureDate] = useState("");
  const [returnDate, setReturnDate] = useState("");
  const [passengers, setPassengers] = useState(1);
  const [cabin, setCabin] = useState("economy");
  const autoRunRef = useRef(false);

  // A question handed over from the dashboard (/flights?q=...) fills the form.
  // The router and the text parser are merged per field, so a date the router
  // dropped is still recovered from the same sentence. A date neither of them
  // found stays blank on purpose — Search stays disabled until the user picks
  // it, which is safer than guessing a date and running a search nobody asked
  // for.
  useEffect(() => {
    if (!initialQuery && !initialFields) return;
    const p = mergeFields(initialFields, parseFlightQuery(initialQuery));
    if (p.origin) setOrigin(p.origin);
    if (p.destination) setDestination(p.destination);
    if (p.departure_date) setDepartureDate(p.departure_date);
    if (p.return_date) setReturnDate(p.return_date);
    if (p.passengers) setPassengers(p.passengers);
    if (p.cabin) setCabin(p.cabin);
  }, [initialQuery, initialFields]);

  const buildQuery = () => {
    // Structured form -> single NL string for the LLM extract node.
    let q = `Find flights from ${origin.trim()} to ${destination.trim()} on ${departureDate}`;
    if (returnDate) q += ` returning ${returnDate}`;
    if (passengers > 1) q += ` for ${passengers} passengers`;
    if (cabin !== "economy") q += ` in ${cabin.replace("_", " ")}`;
    return q;
  };

  const valid = origin.trim() && destination.trim() && departureDate;

  // The router hands over with autoRun only when it had origin, destination AND
  // departure_date. This effect runs after the prefill effect has settled the
  // state, so `valid` is finally truthful - and it is the same expression the
  // Search button uses, so the search can never fire on a form the user would
  // have found unsubmittable. A missing date simply means this never fires and
  // the user picks it.
  useEffect(() => {
    if (!autoRun || autoRunRef.current || loading) return;
    if (!valid) return;
    autoRunRef.current = true;
    onSearch(buildQuery());
  }, [autoRun, valid, loading, origin, destination, departureDate, returnDate, passengers, cabin, onSearch]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!valid || loading) return;
    onSearch(buildQuery());
  };

  const fillSuggestion = (s) => {
    // "Delhi to Dubai" -> origin/destination; user still picks date.
    const m = s.match(/(.+?)\s+to\s+(.+)/i);
    if (m) {
      setOrigin(m[1].trim());
      setDestination(m[2].trim());
    }
  };

  return (
    <div className="search-hero">
      <form className="fl-form" onSubmit={handleSubmit}>
        <div className="fl-grid">
          <label className="fl-field">
            <span><Plane size={13} /> From</span>
            <input
              type="text"
              value={origin}
              onChange={(e) => setOrigin(e.target.value)}
              placeholder="City (e.g. Delhi)"
              className="fl-input"
              disabled={loading}
              required
            />
          </label>
          <label className="fl-field">
            <span><Plane size={13} /> To</span>
            <input
              type="text"
              value={destination}
              onChange={(e) => setDestination(e.target.value)}
              placeholder="City (e.g. Dubai)"
              className="fl-input"
              disabled={loading}
              required
            />
          </label>
          <label className="fl-field">
            <span>Departure</span>
            <input type="date" value={departureDate} min={todayISO()} onChange={(e) => setDepartureDate(e.target.value)} className="fl-input" disabled={loading} required />
          </label>
          <label className="fl-field">
            <span>Return (optional)</span>
            <input type="date" value={returnDate} min={departureDate || todayISO()} onChange={(e) => setReturnDate(e.target.value)} className="fl-input" disabled={loading} />
          </label>
          <label className="fl-field">
            <span>Passengers</span>
            <input type="number" min={1} max={9} value={passengers} onChange={(e) => setPassengers(parseInt(e.target.value) || 1)} className="fl-input" disabled={loading} />
          </label>
          <label className="fl-field">
            <span>Class</span>
            <select value={cabin} onChange={(e) => setCabin(e.target.value)} className="fl-input" disabled={loading}>
              <option value="economy">Economy</option>
              <option value="premium_economy">Premium Economy</option>
              <option value="business">Business</option>
              <option value="first">First</option>
            </select>
          </label>
        </div>
        <div className="search-row">
          <button type="submit" disabled={loading || !valid} className="search-btn">
            {loading ? (
              <span className="btn-loading"><span className="spinner-small" /> Searching</span>
            ) : (
              <><Search size={16} /> Search Flights <ArrowRight size={16} /></>
            )}
          </button>
        </div>
        <div className="search-suggestions">
          <span className="sugg-label"><Sparkles size={12} /> Try:</span>
          {suggestions.map((s) => (
            <button key={s} type="button" className="sugg-chip" onClick={() => fillSuggestion(s)} disabled={loading}>{s}</button>
          ))}
        </div>
        <p className="search-hint"><span className="dot-pulse" /> Live Google Flights results</p>
      </form>
    </div>
  );
}
