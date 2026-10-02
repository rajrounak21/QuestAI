import { currencySymbol } from "../api";

function fmt(amount, currency) {
  if (amount === null || amount === undefined) return null;
  return `${currencySymbol(currency)}${Math.round(amount).toLocaleString("en-US")}`;
}

// Route banner + budget bar. Reads TripSession.to_dict() shape.
export default function TripOverview({ trip }) {
  if (!trip || !trip.destination) return null;
  const b = trip.budget || {};
  const cur = b.currency || "USD";
  const spent = (b.flight_actual || 0) + (b.hotel_actual || 0) + (b.activities_estimated || 0);
  const pct = b.max_total ? Math.min(100, Math.round((spent / b.max_total) * 100)) : null;
  const over = b.max_total != null && spent > b.max_total;

  return (
    <div className="trip-overview">
      <div className="trip-route">
        <h2>{trip.origin} → {trip.destination}</h2>
        <p>
          {[trip.departure_date, trip.return_date].filter(Boolean).join(" → ")}
          {trip.duration_days ? ` · ${trip.duration_days} days` : ""}
          {trip.travelers ? ` · ${trip.travelers} travelers` : ""}
          {trip.status ? <span className={`trip-status ${trip.status}`}> · {trip.status}</span> : null}
        </p>
        {(trip.interests || []).length > 0 && (
          <p className="ext-text">Interests: {trip.interests.join(", ")}</p>
        )}
      </div>
      <div className="trip-budget">
        <div className="trip-budget-row">
          <span>Flights <strong>{fmt(b.flight_actual, cur) || "—"}</strong></span>
          <span>Hotel <strong>{fmt(b.hotel_actual, cur) || "—"}</strong></span>
          <span>Activities <strong>{fmt(b.activities_estimated, cur) || "—"}</strong></span>
          <span className={over ? "trip-over" : ""}>
            {b.max_total != null ? `Budget ${fmt(b.max_total, cur)}` : "No budget set"}
            {spent > 0 && <strong> · Est. {fmt(spent, cur)}</strong>}
          </span>
        </div>
        {pct !== null && (
          <div className="trip-budget-bar">
            <div className={`trip-budget-fill${over ? " over" : ""}`} style={{ width: `${pct}%` }} />
          </div>
        )}
        {over && <p className="trip-over">Over budget — try the chat below to cut costs.</p>}
        {trip.selected_flight && (
          <p className="ext-text">
            ✈ {trip.selected_flight.airline} {trip.selected_flight.flight_number}
            {trip.selected_hotel && (
              <> · 🏨 {trip.selected_hotel.name}</>
            )}
          </p>
        )}
      </div>
    </div>
  );
}
