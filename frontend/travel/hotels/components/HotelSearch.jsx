import { useEffect, useState } from "react";
import { Search, ArrowRight, Sparkles, Building2 } from "lucide-react";
import { parseHotelQuery } from "../../shared/parseQuery";

const suggestions = ["Dubai", "Bali", "London"];

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

export default function HotelSearch({ onSearch, loading, initialQuery = "", initialFields = null }) {
  const [location, setLocation] = useState("");
  const [checkIn, setCheckIn] = useState("");
  const [checkOut, setCheckOut] = useState("");
  const [guests, setGuests] = useState(2);

  // A question handed over from the dashboard (/hotels?q=...) fills the form and
  // nothing more. Fields the universal router already extracted win; anything it
  // left out is filled by the text parser. Dates it could not find stay blank
  // on purpose — the Search button stays disabled until the user picks them,
  // rather than guessing a date and running a search nobody asked for.
  useEffect(() => {
    if (!initialQuery && !initialFields) return;
    const p = initialFields || parseHotelQuery(initialQuery) || {};
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
        <p className="search-hint"><span className="dot-pulse" /> Live Google Hotels · pick a city, we handle the rest</p>
      </form>
    </div>
  );
}
