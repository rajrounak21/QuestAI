import { ArrowUpRight } from "lucide-react";
import { currencySymbol } from "../api";

function formatPrice(price, currency) {
  if (!price || price <= 0) return null;
  return `${currencySymbol(currency)}${Math.round(price).toLocaleString("en-US")}`;
}

function fmtTime(t) {
  if (!t) return "";
  const parts = String(t).split(" ");
  return parts.length >= 2 ? parts[1] : t;
}

export default function FlightCard({ flight, onSelect, highlight, selected }) {
  const stops = flight.stops === 0 ? "Non-stop" : flight.stops === 1 ? "1 stop" : `${flight.stops} stops`;
  const open = () => onSelect && onSelect(flight);
  return (
    <div className="shopping-card fl-card" onClick={open} style={{ cursor: onSelect ? "pointer" : undefined }}>
      {(highlight?.cheapest || highlight?.fastest || selected) && (
        <div className="fl-ribbons">
          {selected && <span className="fl-ribbon selected">✓ Selected</span>}
          {highlight?.cheapest && <span className="fl-ribbon cheap">Cheapest</span>}
          {highlight?.fastest && <span className="fl-ribbon fast">Fastest</span>}
        </div>
      )}
      <div className="shopping-info">
        <p className="shopping-store">
          {flight.airline_logo && (
            <img src={flight.airline_logo} alt={flight.airline} style={{ width: 18, height: 18, objectFit: "contain" }} onError={(e) => { e.target.style.display = "none"; }} />
          )}
          {flight.airline} · {flight.flight_number}
        </p>
        <h3 className="shopping-title">
          {flight.departure?.airport} {fmtTime(flight.departure?.time)} → {flight.arrival?.airport} {fmtTime(flight.arrival?.time)}
        </h3>
        <div className="shopping-meta">
          <span className="shopping-rating">{flight.duration_display}</span>
          <span className="meta-dot">·</span>
          {flight.stops === 0 ? (
            <span className="nonstop-pill">Non-stop</span>
          ) : (
            <span className="ext-text">{stops}</span>
          )}
        </div>
        <div className="shopping-price-row">
          {formatPrice(flight.price, flight.currency) ? (
            <span className="shopping-price">{formatPrice(flight.price, flight.currency)}</span>
          ) : (
            <span className="price-unavailable">Price unavailable</span>
          )}
        </div>
        {onSelect && (
          <button className="shopping-view-btn" onClick={(e) => { e.stopPropagation(); open(); }}>
            Open Details <ArrowUpRight size={14} />
          </button>
        )}
      </div>
    </div>
  );
}
