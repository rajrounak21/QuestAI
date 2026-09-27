const CURRENCY_SYMBOLS = {
  USD: '$', EUR: '\u20AC', GBP: '\u00A3', INR: '\u20B9', JPY: '\u00A5', CNY: '\u00A5', AED: 'AED ', SAR: 'SAR ', SGD: 'S$ ', CAD: 'C$ ', AUD: 'A$ ',
};

function formatPrice(price, currency) {
  if (!price || price === 0) return null;
  const symbol = CURRENCY_SYMBOLS[currency] || currency + ' ';
  return `${symbol}${Math.round(price).toLocaleString()}`;
}

export default function FlightCard({ flight, onSelect }) {
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
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }
    return '';
  };

  const stopText = flight.stops === 0
    ? 'Non-stop'
    : flight.stops === 1
    ? '1 stop'
    : `${flight.stops} stops`;

  return (
    <div className="flight-card" onClick={() => onSelect(flight)}>
      <div className="card-header">
        <div className="airline-info">
          {flight.airline_logo && (
            <img
              src={flight.airline_logo}
              alt={flight.airline}
              className="airline-logo"
              onError={(e) => { e.target.style.display = 'none'; }}
            />
          )}
          <span className="airline-name">{flight.airline}</span>
        </div>
        <div className="price">
          {formatPrice(flight.price, flight.currency) ? (
            <span className="amount">{formatPrice(flight.price, flight.currency)}</span>
          ) : (
            <span className="price-unavailable">View for price</span>
          )}
        </div>
      </div>

      <div className="card-route">
        <div className="airport">
          <span className="code">{flight.departure.airport}</span>
          <span className="time">{formatTime(flight.departure.time)}</span>
        </div>

        <div className="route-line">
          <div className="line"></div>
          <div className="duration">{flight.duration_display}</div>
          <div className="line"></div>
        </div>

        <div className="airport">
          <span className="code">{flight.arrival.airport}</span>
          <span className="time">{formatTime(flight.arrival.time)}</span>
        </div>
      </div>

      <div className="card-footer">
        <span className="stops">{stopText}</span>
        <span className="flight-number">{flight.flight_number}</span>
      </div>
    </div>
  );
}
