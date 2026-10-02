import { useState } from "react";
import { flightsApi } from "../api";
import { PriceDisclaimer } from "../../../src/shared/TravelGuide";

const CURRENCY_SYMBOLS = {
  USD: '$', EUR: '€', GBP: '£', INR: '₹', JPY: '¥', CNY: '¥', AED: 'AED ', SAR: 'SAR ', SGD: 'S$ ', CAD: 'C$ ', AUD: 'A$ ',
};

function formatPrice(price, currency) {
  if (!price || price === 0) return null;
  const symbol = CURRENCY_SYMBOLS[currency] || currency + ' ';
  return `${symbol}${Math.round(price).toLocaleString()}`;
}

function BookingOptionRow({ option, currency, showTotal }) {
  const price = typeof option.price === "number" && option.price > 0
    ? formatPrice(option.price, currency)
    : null;
  // booking_request must be POSTed exactly as given (Google redirect that
  // lands on the provider checkout). post_data looks like "u=<payload>".
  let postName = null;
  let postValue = null;
  if (option.booking_post_data && option.booking_post_data.includes("=")) {
    const idx = option.booking_post_data.indexOf("=");
    postName = option.booking_post_data.slice(0, idx);
    postValue = option.booking_post_data.slice(idx + 1);
  }
  return (
    <div className={`booking-opt${option.airline ? " airline-direct" : ""}`}>
      <div className="booking-opt-info">
        <strong>{option.book_with || "Provider"}</strong>
        {option.leg === "departing" && <span className="leg-chip going">Going ticket</span>}
        {option.leg === "returning" && <span className="leg-chip back">Back ticket</span>}
        {option.airline && <span className="airline-direct-badge">✈ Airline direct</span>}
        {option.option_title && <span className="ext-text">{option.option_title}</span>}
        {(option.extensions || []).slice(0, 2).map((e, i) => (
          <span key={i} className="ext-text">· {e}</span>
        ))}
      </div>
      <div className="booking-opt-action">
        {price && (
          <span className="booking-opt-price">
            <span className="shopping-price">{price}</span>
            {showTotal && <span className="price-caption">total</span>}
          </span>
        )}
        {option.booking_url && postName ? (
          <form action={option.booking_url} method="POST" target="_blank" rel="noopener noreferrer">
            <input type="hidden" name={postName} value={postValue} />
            <button type="submit" className="btn-again">Book</button>
          </form>
        ) : option.booking_url ? (
          <a href={option.booking_url} target="_blank" rel="noopener noreferrer" className="btn-again">
            Book
          </a>
        ) : null}
      </div>
    </div>
  );
}

export default function FlightDetails({ flight, searchContext, onClose, onSelect, isSelected }) {
  const [options, setOptions] = useState(null);
  const [optsLoading, setOptsLoading] = useState(false);
  const [optsError, setOptsError] = useState("");
  const [returnOptions, setReturnOptions] = useState([]);
  const [returnIdx, setReturnIdx] = useState(0);
  const [pickingIdx, setPickingIdx] = useState(null);

  if (!flight) return null;

  const datePart = (t) => String(t || "").split(" ")[0] || "";
  const formatReturnDate = (iso) => {
    if (!iso) return "";
    const d = new Date(`${iso}T00:00:00`);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
  };
  const hasToken = Boolean(flight.booking_token || flight.departure_token);

  // Traveler count: flights page params use `passengers`, trips use `travelers`.
  // Booking lookups must price for the same headcount as the search.
  const _sctx = searchContext || {};
  const travelers = Math.max(1, parseInt(_sctx.passengers ?? _sctx.travelers ?? 1, 10) || 1);

  // Trip origin/destination are city names ("Delhi"); the booking lookup
  // needs 3-letter IATA codes, which live on the flight itself ("DEL").
  // Always prefer a valid code from the flight, fall back to context.
  const iata = (s) => {
    const v = String(s || "").trim().toUpperCase();
    return /^[A-Z]{3}$/.test(v) ? v : "";
  };
  const ctxIds = () => {
    const ctx = searchContext || {};
    return {
      departure_id: iata(flight.departure?.airport) || iata(ctx.origin),
      arrival_id: iata(flight.arrival?.airport) || iata(ctx.destination),
      outbound_date: ctx.departure_date || datePart(flight.departure?.time),
      ctx,
    };
  };

  // Normalized segments -> pair-booking shape (both legs booked together).
  const toSegs = (segs) =>
    (segs || [])
      .map((s) => ({
        flight_number: String(s.flight_number || "").replace(/\s+/g, ""),
        departure_id: s.departure?.airport || "",
        arrival_id: s.arrival?.airport || "",
        date: datePart(s.departure?.time),
      }))
      .filter((s) => s.flight_number && s.departure_id && s.arrival_id && s.date);

  const loadOptions = async () => {
    if (!hasToken || optsLoading) return;
    // Original search context (SerpApi needs it alongside the token).
    // Fall back to the flight's own endpoints for old saved sessions.
    const { departure_id, arrival_id, outbound_date, ctx } = ctxIds();
    if (!departure_id || !arrival_id || !outbound_date) {
      setOptsError("Not enough flight details to load booking options.");
      return;
    }
    setOptsLoading(true);
    setOptsError("");
    try {
      const outSegs = toSegs(flight.segments);
      const data = await flightsApi.bookingOptions({
        ...(flight.booking_token
          ? { booking_token: flight.booking_token }
          : { departure_token: flight.departure_token }),
        // Round trip: pin BOTH legs so one booking covers going + back.
        ...(outSegs.length > 0 && ctx.return_date ? { outbound_flights: outSegs } : {}),
        departure_id,
        arrival_id,
        outbound_date,
        ...(ctx.return_date ? { return_date: ctx.return_date } : {}),
        ...(ctx.trip_type ? { trip_type: ctx.trip_type } : {}),
        currency: flight.currency || "USD",
        travelers,
      });
      setOptions(data.options || []);
      setReturnOptions(data.return_options || []);
      setReturnIdx(0);
    } catch (e) {
      setOptsError(e.message || "Could not load booking options.");
    } finally {
      setOptsLoading(false);
    }
  };

  // Round trip: user picks a different return leg -> pair-book going +
  // that return in one booking (1 extra search, user-initiated).
  // pickingIdx drives per-row spinner + list dimming so the 5-10s reload
  // never looks dead.
  const pickReturn = async (i) => {
    const cand = returnOptions[i];
    if (!cand || optsLoading || i === returnIdx) return;
    const outSegs = toSegs(flight.segments);
    if (outSegs.length === 0 || !cand.segments || cand.segments.length === 0) {
      setOptsError("This saved flight is missing segment details — search again for live booking.");
      return;
    }
    const { departure_id, arrival_id, outbound_date, ctx } = ctxIds();
    setOptsLoading(true);
    setPickingIdx(i);
    setOptsError("");
    try {
      const data = await flightsApi.bookingOptions({
        outbound_flights: outSegs,
        return_flights: cand.segments,
        departure_id,
        arrival_id,
        outbound_date,
        ...(ctx.return_date ? { return_date: ctx.return_date } : {}),
        ...(ctx.trip_type ? { trip_type: ctx.trip_type } : {}),
        currency: flight.currency || "USD",
        travelers,
      });
      setOptions(data.options || []);
      setReturnIdx(i);
    } catch (e) {
      setOptsError(e.message || "Could not load booking options.");
    } finally {
      setOptsLoading(false);
      setPickingIdx(null);
    }
  };

  const formatTime = (timeStr) => {
    if (!timeStr) return '';
    const parts = timeStr.split(' ');
    if (parts.length >= 2) {
      return parts[1];
    }
    return timeStr;
  };

  const formatDate = (timeStr) => {
    if (!timeStr) return '';
    const parts = timeStr.split(' ');
    if (parts.length >= 1) {
      const date = new Date(parts[0]);
      return date.toLocaleDateString('en-US', {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      });
    }
    return '';
  };

  // Split once for grouped rendering below (combo totals vs per-leg tickets).
  const isRoundTrip = returnOptions.length > 0;
  const sortOpts = (list) => list.slice().sort((a, b) => {
    // Airline-direct first, then cheapest.
    if (!!a.airline !== !!b.airline) return a.airline ? -1 : 1;
    return (a.price ?? Infinity) - (b.price ?? Infinity);
  });
  const comboOpts = sortOpts((options || []).filter((o) => !o.leg || o.leg === "together"));
  const goingOpts = sortOpts((options || []).filter((o) => o.leg === "departing"));
  const backOpts = sortOpts((options || []).filter((o) => o.leg === "returning"));
  const separateOpts = [...goingOpts, ...backOpts];

  return (
    <div className="flight-details-overlay" onClick={onClose}>
      <div className="flight-details-modal" onClick={(e) => e.stopPropagation()}>
        <button className="close-btn" onClick={onClose}>
          ×
        </button>

        <div className="details-header">
          <div className="airline-info">
            {flight.airline_logo && (
              <img
                src={flight.airline_logo}
                alt={flight.airline}
                className="airline-logo-large"
                onError={(e) => { e.target.style.display = 'none'; }}
              />
            )}
            <div>
              <h3>{flight.airline}</h3>
              <p className="flight-number">{flight.flight_number}</p>
            </div>
          </div>
          <div className="price-large">
            {formatPrice(flight.price, flight.currency) ? (
              <span className="amount">{formatPrice(flight.price, flight.currency)}</span>
            ) : (
              <span className="price-unavailable">View for price</span>
            )}
          </div>
        </div>

        <div className="itinerary">
          {(flight.segments || []).map((segment, index) => (
            <div key={index} className="segment">
              <div className="segment-point">
                <span className="airport-code">{segment.departure.airport}</span>
                <span className="time">{formatTime(segment.departure.time)}</span>
                <span className="date">{formatDate(segment.departure.time)}</span>
              </div>

              <div className="segment-line">
                <div className="line"></div>
                <div className="duration">{segment.duration}m</div>
                <div className="line"></div>
              </div>

              <div className="segment-point">
                <span className="airport-code">{segment.arrival.airport}</span>
                <span className="time">{formatTime(segment.arrival.time)}</span>
                <span className="date">{formatDate(segment.arrival.time)}</span>
              </div>

              <div className="segment-info">
                <span>{segment.airline} {segment.flight_number}</span>
                {segment.aircraft && <span>· {segment.aircraft}</span>}
                {segment.travel_class && <span>· {segment.travel_class}</span>}
              </div>

              {index < (flight.segments || []).length - 1 && (flight.stop_details || [])[index] && (
                <div className="layover">
                  <span className="layover-icon">↓</span>
                  <span className="layover-text">
                    Layover at {flight.stop_details[index].airport} ({flight.stop_details[index].duration})
                  </span>
                </div>
              )}
            </div>
          ))}
        </div>

        {hasToken ? (
          <div className="booking-opts booking-spotlight">
            <div className="booking-opts-head">
              <h4>{isRoundTrip ? "✈ Book this round trip" : "✈ Book this flight"}</h4>
              {options === null && (
                <button className="search-btn booking-cta" disabled={optsLoading} onClick={loadOptions}>
                  {optsLoading ? "Loading…" : "Show booking options"}
                </button>
              )}
            </div>
            {isRoundTrip ? (
              <p className="booking-opts-note">
                Going flight (shown above) + picked return below — <strong>one booking</strong> covers both.
                Every price here is the <strong>full round-trip total</strong> — picking another return recomputes all prices.
              </p>
            ) : (
              <p className="booking-opts-note">Direct airline &amp; agent prices for this exact flight.</p>
            )}
            {travelers > 1 && (
              <p className="booking-opts-note">Prices for {travelers} travelers.</p>
            )}
            {returnOptions.length > 0 && (
              <div className="return-picker">
                <p className="booking-opts-note">
                  ✈ Back home {formatReturnDate((searchContext || {}).return_date)} — pick your return flight:
                </p>
                {returnOptions.map((r, i) => (
                  <button
                    key={i}
                    type="button"
                    disabled={optsLoading}
                    onClick={() => pickReturn(i)}
                    className={`return-opt${i === returnIdx ? " active" : ""}`}
                  >
                    <span className="return-opt-radio">
                      {pickingIdx === i ? <span className="spinner-small" /> : (i === returnIdx ? "●" : "○")}
                    </span>
                    <span className="return-opt-main">
                      <strong>{r.dep_time || "–"} → {r.arr_time || "–"}</strong>
                      <span className="ext-text">
                        {[r.flight_no, r.stops === 0 ? "Non-stop" : r.stops === 1 ? "1 stop" : `${r.stops} stops`].filter(Boolean).join(" · ")}
                      </span>
                    </span>
                    {typeof r.price === "number" && r.price > 0 && (
                      <span className="return-opt-price">
                        <span className="shopping-price">
                          {formatPrice(r.price, flight.currency)}
                        </span>
                        <span className="price-caption">trip total</span>
                      </span>
                    )}
                  </button>
                ))}
              </div>
            )}
            {optsError && <div className="no-results premium">{optsError}</div>}
            {pickingIdx !== null && (
              <p className="booking-opts-note booking-loading">
                <span className="spinner-small" /> Fetching prices for picked return… booking list updates below.
              </p>
            )}
            {options !== null && options.length === 0 && !optsError && (
              <div className="no-results premium">
                {returnOptions.length > 0
                  ? "No booking for this going + return combination — try another return above."
                  : "No booking options found for this flight."}
              </div>
            )}
            <div className={pickingIdx !== null ? "booking-list-dim" : undefined}>
            {comboOpts.length > 0 && (
              <>
                {separateOpts.length > 0 && (
                  <p className="booking-opts-note">One booking · both flights · trip total:</p>
                )}
                {comboOpts.map((o, i) => (
                  <BookingOptionRow key={`c-${i}`} option={o} currency={flight.currency} showTotal={isRoundTrip} />
                ))}
              </>
            )}
            {separateOpts.length > 0 && (
              <>
                <p className="booking-opts-note">Separate tickets — book each leg:</p>
                {separateOpts.map((o, i) => (
                  <BookingOptionRow key={`s-${i}`} option={o} currency={flight.currency} />
                ))}
              </>
            )}
            </div>
            <PriceDisclaimer compact />
          </div>
        ) : (
          <p className="booking-opts-note" style={{ marginTop: 12 }}>
            Booking options need a fresh search — this is a saved result. Search again for live “Book with” prices.
          </p>
        )}

        <div className="details-footer">
          <div className="flight-meta">
            <span>{flight.stops === 0 ? 'Non-stop' : `${flight.stops} stop(s)`}</span>
            <span>·</span>
            <span>{flight.duration_display}</span>
          </div>
          {onSelect && (
            <button
              className="search-btn booking-cta"
              disabled={isSelected}
              onClick={() => onSelect(flight)}
            >
              {isSelected ? "✓ Selected" : "Select this flight"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
