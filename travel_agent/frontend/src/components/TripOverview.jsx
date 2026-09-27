export default function TripOverview({ trip, onSelectFlight, onSelectHotel, onViewFlight, onViewHotel }) {
  const formatDate = (dateStr) => {
    if (!dateStr) return 'TBD';
    const date = new Date(dateStr + 'T00:00:00');
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const formatDuration = (mins) => {
    if (!mins) return '';
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return `${h}h ${m}m`;
  };

  const budget = trip.budget || {};
  const maxBudget = budget.max_total || 0;
  const flights = (trip.flight_results || []).slice(0, 5);
  const hotels = (trip.hotel_results || []).slice(0, 5);
  const selectedFlightId = trip.selected_flight?.id;
  const selectedHotelId = trip.selected_hotel?.id;

  const handleFlightClick = (flight) => {
    onSelectFlight?.(flight);
    onViewFlight?.(flight);
  };

  const handleHotelClick = (hotel) => {
    onSelectHotel?.(hotel);
    onViewHotel?.(hotel);
  };

  return (
    <div className="trip-overview">
      <div className="trip-route">
        <span className="trip-origin">{trip.origin || 'Origin'}</span>
        <span className="trip-arrow">→</span>
        <span className="trip-destination">{trip.destination}</span>
      </div>

      <div className="trip-meta">
        <span>{formatDate(trip.departure_date)} – {formatDate(trip.return_date)}</span>
        <span>·</span>
        <span>{trip.travelers} Traveler{trip.travelers !== 1 ? 's' : ''}</span>
        {trip.duration_days && (
          <>
            <span>·</span>
            <span>{trip.duration_days} Days</span>
          </>
        )}
      </div>

      {flights.length > 0 && (
        <div className="trip-options-section">
          <h3>✈️ Flight Options</h3>
          <div className="options-grid">
            {flights.map((flight) => {
              const isSelected = flight.id === selectedFlightId;
              const stops = flight.stops === 0 ? 'Nonstop' : `${flight.stops} stop${flight.stops > 1 ? 's' : ''}`;
              return (
                <div
                  key={flight.id}
                  className={`option-card ${isSelected ? 'selected' : ''}`}
                  onClick={() => handleFlightClick(flight)}
                >
                  {isSelected && <div className="selected-badge">Selected</div>}
                  <div className="option-header">
                    <span className="option-airline">
                      {flight.airline_logo && (
                        <img src={flight.airline_logo} alt="" className="airline-logo" />
                      )}
                      {flight.airline}
                    </span>
                    <span className="option-price">${flight.price}</span>
                  </div>
                  <div className="option-details">
                    <span>{flight.flight_number}</span>
                    <span>{stops}</span>
                    <span>{formatDuration(flight.duration)}</span>
                  </div>
                  <div className="option-route-small">
                    <span>{flight.departure?.airport}</span>
                    <span className="option-arrow">→</span>
                    <span>{flight.arrival?.airport}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {hotels.length > 0 && (
        <div className="trip-options-section">
          <h3>🏨 Hotel Options</h3>
          <div className="options-grid">
            {hotels.map((hotel) => {
              const isSelected = hotel.id === selectedHotelId;
              const withinBudget = maxBudget > 0 && hotel.price_per_night <= (maxBudget * 0.4) / Math.max(1, trip.duration_days || 5);
              return (
                <div
                  key={hotel.id}
                  className={`option-card ${isSelected ? 'selected' : ''} ${withinBudget ? 'budget-ok' : ''}`}
                  onClick={() => handleHotelClick(hotel)}
                >
                  {isSelected && <div className="selected-badge">Selected</div>}
                  {hotel.deal && <div className="deal-badge">{hotel.deal}</div>}
                  <div className="option-header">
                    <span className="option-name">{hotel.name}</span>
                    <span className="option-price">${hotel.price_per_night}<small>/night</small></span>
                  </div>
                  <div className="option-details">
                    {hotel.hotel_class && <span>{'★'.repeat(hotel.hotel_class)}</span>}
                    {hotel.rating && <span>{hotel.rating} ★</span>}
                    {hotel.reviews && <span>({hotel.reviews.toLocaleString()})</span>}
                  </div>
                  {hotel.total_price > 0 && (
                    <div className="option-total">Total: ${hotel.total_price}</div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {flights.length === 0 && hotels.length === 0 && trip.selected_flight && (
        <div className="trip-sections">
          <div className="trip-section">
            <span className="section-icon">✈️</span>
            <div className="section-content">
              <span className="section-label">Flights</span>
              <span className="section-value">
                {trip.selected_flight.airline} {trip.selected_flight.flight_number}
              </span>
              {trip.selected_flight.price && (
                <span className="section-price">${trip.selected_flight.price}</span>
              )}
            </div>
          </div>
          {trip.selected_hotel && (
            <div className="trip-section">
              <span className="section-icon">🏨</span>
              <div className="section-content">
                <span className="section-label">Stay</span>
                <span className="section-value">
                  {trip.selected_hotel.name}
                  {trip.selected_hotel.hotel_class && ` · ${trip.selected_hotel.hotel_class}-Star`}
                </span>
                {trip.selected_hotel.price_per_night && (
                  <span className="section-price">${trip.selected_hotel.price_per_night}/night</span>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
