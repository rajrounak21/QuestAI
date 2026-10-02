import { PriceDisclaimer } from "../../../src/shared/TravelGuide";

const CURRENCY_SYMBOLS = {
  USD: '$', EUR: '€', GBP: '£', INR: '₹', AED: 'AED ', SAR: 'SAR ',
};

function formatPrice(price, currency) {
  if (!price || price === 0) return null;
  const symbol = CURRENCY_SYMBOLS[currency] || currency + ' ';
  return `${symbol}${Math.round(price).toLocaleString()}`;
}

export default function HotelDetails({ hotel, onClose, onSelect, isSelected }) {
  if (!hotel) return null;

  const priceStr = formatPrice(hotel.price_per_night, hotel.currency);
  const totalStr = formatPrice(hotel.total_price, hotel.currency);

  return (
    <div className="hotel-details-overlay" onClick={onClose}>
      <div className="hotel-details-modal" onClick={(e) => e.stopPropagation()}>
        <button className="close-btn" onClick={onClose}>
          ×
        </button>

        <div className="hotel-details-image">
          {hotel.image ? (
            <img src={hotel.image} alt={hotel.name} />
          ) : (
            <div className="no-image-large">No Image Available</div>
          )}
        </div>

        <div className="hotel-details-content">
          <div className="hotel-details-header">
            <div>
              <h2>{hotel.name}</h2>
              {hotel.hotel_class && (
                <span className="hotel-stars-large">{'★'.repeat(hotel.hotel_class)}</span>
              )}
            </div>
            <div className="hotel-details-price">
              {priceStr ? (
                <>
                  <span className="price-amount">{priceStr}</span>
                  <span className="price-label">/night</span>
                </>
              ) : (
                <span className="price-unavailable">View for price</span>
              )}
            </div>
          </div>

          <div className="hotel-details-rating">
            {hotel.rating && (
              <span className="rating-badge">★ {hotel.rating.toFixed(1)}</span>
            )}
            {hotel.reviews && (
              <span className="review-count">{hotel.reviews.toLocaleString()} reviews</span>
            )}
          </div>

          {(hotel.address || hotel.maps_link) && (
            <div className="hotel-details-location">
              {hotel.address && <span>📍 {hotel.address}</span>}
              {hotel.maps_link && (
                <a href={hotel.maps_link} target="_blank" rel="noopener noreferrer" className="auth-link">
                  View on map →
                </a>
              )}
            </div>
          )}

          <div className="hotel-details-times">
            {hotel.check_in_time && (
              <span>Check-in: {hotel.check_in_time}</span>
            )}
            {hotel.check_out_time && (
              <span>Check-out: {hotel.check_out_time}</span>
            )}
          </div>

          <div className="hotel-details-amenities">
            <h4>Amenities</h4>
            <div className="amenities-grid">
              {(hotel.amenities || []).map((amenity, i) => (
                <div key={i} className="amenity-item">
                  <span className="amenity-check">✓</span>
                  <span>{amenity}</span>
                </div>
              ))}
            </div>
          </div>

          {totalStr && (
            <div className="hotel-details-total">
              <span>Total for stay:</span>
              <span className="total-price">{totalStr}</span>
            </div>
          )}

          {hotel.free_cancellation && (
            <div className="free-cancel-note">✓ Free cancellation available</div>
          )}

          {hotel.deal && (
            <div className="deal-note">🏷️ {hotel.deal}</div>
          )}

          {hotel.booking_link && (
            <a
              href={hotel.booking_link}
              target="_blank"
              rel="noopener noreferrer"
              className="book-btn"
            >
              View / Book Hotel
            </a>
          )}
          <PriceDisclaimer compact />

          {onSelect && (
            <button
              className="book-btn select-btn"
              disabled={isSelected}
              onClick={() => onSelect(hotel)}
              style={{ marginTop: 8 }}
            >
              {isSelected ? "✓ Selected for this trip" : "Select this hotel"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
