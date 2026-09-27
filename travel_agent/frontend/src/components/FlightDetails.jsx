const CURRENCY_SYMBOLS = {
  USD: '$', EUR: '\u20AC', GBP: '\u00A3', INR: '\u20B9', JPY: '\u00A5', CNY: '\u00A5', AED: 'AED ', SAR: 'SAR ', SGD: 'S$ ', CAD: 'C$ ', AUD: 'A$ ',
};

function formatPrice(price, currency) {
  if (!price || price === 0) return null;
  const symbol = CURRENCY_SYMBOLS[currency] || currency + ' ';
  return `${symbol}${Math.round(price).toLocaleString()}`;
}

export default function FlightDetails({ flight, onClose }) {
  if (!flight) return null;

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
          {flight.segments.map((segment, index) => (
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

              {index < flight.segments.length - 1 && flight.stop_details[index] && (
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

        <div className="details-footer">
          <div className="flight-meta">
            <span>{flight.stops === 0 ? 'Non-stop' : `${flight.stops} stop(s)`}</span>
            <span>·</span>
            <span>{flight.duration_display}</span>
          </div>
          {flight.booking_link && (
            <a
              href={flight.booking_link}
              target="_blank"
              rel="noopener noreferrer"
              className="book-btn"
            >
              View / Book Flight
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
