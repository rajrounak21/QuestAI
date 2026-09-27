const CURRENCY_SYMBOLS = {
  USD: '$', EUR: '\u20AC', GBP: '\u00A3', INR: '\u20B9', AED: 'AED ', SAR: 'SAR ',
};

function formatPrice(price, currency) {
  if (!price || price === 0) return null;
  const symbol = CURRENCY_SYMBOLS[currency] || currency + ' ';
  return `${symbol}${Math.round(price).toLocaleString()}`;
}

function StarRating({ rating }) {
  if (!rating) return null;
  const stars = Math.round(rating);
  return (
    <span className="star-rating">
      {'★'.repeat(stars)}{'☆'.repeat(5 - stars)}
    </span>
  );
}

export default function HotelCard({ hotel, onSelect }) {
  const priceStr = formatPrice(hotel.price_per_night, hotel.currency);
  const totalStr = formatPrice(hotel.total_price, hotel.currency);

  return (
    <div className="hotel-card" onClick={() => onSelect(hotel)}>
      <div className="hotel-image">
        {hotel.image ? (
          <img
            src={hotel.image}
            alt={hotel.name}
            onError={(e) => { e.target.src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="300" height="200" fill="%23ddd"><rect width="300" height="200"/><text x="150" y="100" text-anchor="middle" fill="%23999" font-size="14">No Image</text></svg>'; }}
          />
        ) : (
          <div className="no-image">No Image</div>
        )}
        {hotel.deal && <span className="deal-badge">{hotel.deal}</span>}
        {hotel.free_cancellation && <span className="cancel-badge">Free Cancel</span>}
      </div>

      <div className="hotel-info">
        <div className="hotel-header">
          <h3 className="hotel-name">{hotel.name}</h3>
          {hotel.hotel_class && (
            <span className="hotel-stars">{'★'.repeat(hotel.hotel_class)}</span>
          )}
        </div>

        <div className="hotel-rating">
          {hotel.rating && (
            <span className="rating-score">★ {hotel.rating.toFixed(1)}</span>
          )}
          {hotel.reviews && (
            <span className="review-count">· {hotel.reviews.toLocaleString()} reviews</span>
          )}
        </div>

        <div className="hotel-amenities">
          {hotel.amenities.slice(0, 4).map((amenity, i) => (
            <span key={i} className="amenity-tag">{amenity}</span>
          ))}
          {hotel.amenities.length > 4 && (
            <span className="amenity-more">+{hotel.amenities.length - 4} more</span>
          )}
        </div>

        <div className="hotel-pricing">
          {priceStr ? (
            <>
              <span className="price-per-night">{priceStr} <small>/night</small></span>
              {totalStr && (
                <span className="price-total">{totalStr} total</span>
              )}
            </>
          ) : (
            <span className="price-unavailable">View for price</span>
          )}
        </div>
      </div>
    </div>
  );
}
