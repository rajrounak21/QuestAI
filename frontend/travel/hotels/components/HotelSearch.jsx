import { useEffect, useRef, useState } from "react";
import { Search, ArrowRight, Sparkles, Building2 } from "lucide-react";
import { parseHotelQuery } from "../../shared/parseQuery";
import { mergeFields } from "../../../src/shared/mergeFields";

const suggestions = ["Dubai", "Bali", "London"];

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

export default function HotelSearch({ onSearch, loading, initialQuery = "", initialFields = null, autoRun = false }) {
  const [location, setLocation] = useState("");
  const [checkIn, setCheckIn] = useState("");
  const [checkOut, setCheckOut] = useState("");
  const [guests, setGuests] = useState(2);
  const autoRunRef = useRef(false);

  // A question handed over from the dashboard (/hotels?q=...) fills the form.
  // Merged per field, so dates the router dropped still come from the parser.
  // Dates neither found stay blank on purpose - Search stays disabled until the
  // user picks them rather than guessing a date nobody asked for.
  useEffect(() => {
    if (!initialQuery && !initialFields) return;
    const p = mergeFields(initialFields, parseHotelQuery(initialQuery));
    if (p.location) setLocation(p.location);
    if (p.check_in) setCheckIn(p.check_in);
    if (p.check_out) setCheckOut(p.check_out);
    if (p.guests) setGuests(p.guests);
  }, [initialQuery, initialFields]);

  const valid = location.trim() && checkIn && checkOut;

  const buildQuery = () => {
    // Structured form -> single NL string for the LLM extract node.
    return `Find hotels in ${location.trim()} from ${checkIn} to ${checkOut} for ${guests} guests`;
  };

  // Fires only once the form is genuinely submittable - same `valid` the Search
  // button uses. The router sets autoRun only when it had location and both
  // dates, so a missing date lands the user here with the button disabled and
  // nothing spent.
  useEffect(() => {
    if (!autoRun || autoRunRef.current || loading) return;
    if (!valid) return;
    autoRunRef.current = true;
    onSearch(buildQuery());
  }, [autoRun, valid, loading, location, checkIn, checkOut, guests, onSearch]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!valid || loading) return;
    onSearch(buildQuery());
  };

  return (
    <div className="search-hero">
      <form className="fl-form" onSubmit={handleSubmit}>
        <div className="fl-grid">
          <label className="fl-field">
            <span><Building2 size={13} /> Location</span>
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="City (e.g. Dubai)"
              className="fl-input"
              disabled={loading}
              required
            />
          </label>
          <label className="fl-field">
            <span>Check-in</span>
            <input type="date" value={checkIn} min={todayISO()} onChange={(e) => setCheckIn(e.target.value)} className="fl-input" disabled={loading} required />
          </label>
          <label className="fl-field">
            <span>Check-out</span>
            <input type="date" value={checkOut} min={checkIn || todayISO()} onChange={(e) => setCheckOut(e.target.value)} className="fl-input" disabled={loading} required />
          </label>
          <label className="fl-field">
            <span>Guests</span>
            <input type="number" min={1} max={10} value={guests} onChange={(e) => setGuests(parseInt(e.target.value) || 2)} className="fl-input" disabled={loading} />
          </label>
        </div>
        <div className="search-row">
          <button type="submit" disabled={loading || !valid} className="search-btn">
            {loading ? (
              <span className="btn-loading"><span className="spinner-small" /> Searching</span>
            ) : (
              <><Search size={16} /> Search Hotels <ArrowRight size={16} /></>
            )}
          </button>
        </div>
        <div className="search-suggestions">
          <span className="sugg-label"><Sparkles size={12} /> Try:</span>
          {suggestions.map((s) => (
            <button key={s} type="button" className="sugg-chip" onClick={() => setLocation(s)} disabled={loading}>{s}</button>
          ))}
        </div>
        {!loading && <p className="search-hint"><span className="dot-pulse" /> Live Google Hotels · pick a city, we handle the rest</p>}
      </form>
    </div>
  );
}
