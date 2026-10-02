import { ExternalLink, Star, MapPin } from "lucide-react";
import { currencySymbol } from "../api";

function formatPrice(price, currency) {
  if (!price || price <= 0) return null;
  return `${currencySymbol(currency)}${Math.round(price).toLocaleString("en-US")}`;
}

export default function HotelCard({ hotel, onSelect, selected }) {
  const perNight = formatPrice(hotel.price_per_night, hotel.currency);
  const total = formatPrice(hotel.total_price, hotel.currency);
  return (
    <div className="shopping-card ht-card" onClick={() => onSelect && onSelect(hotel)} style={{ cursor: onSelect ? "pointer" : undefined }}>
      {(selected || (typeof hotel.rating === "number" && hotel.rating >= 4.7)) && (
        <div className="fl-ribbons">
          {selected && <span className="fl-ribbon selected">✓ Selected</span>}
          {typeof hotel.rating === "number" && hotel.rating >= 4.7 && (
            <span className="fl-ribbon cheap">★ Top rated</span>
          )}
        </div>
      )}
      <div className="shopping-image-wrap">
        {hotel.deal && <span className="card-badge top-left">{hotel.deal}</span>}
        {hotel.free_cancellation && <span className="card-badge top-right hot">Free Cancel</span>}
        {hotel.image ? (
          <img src={hotel.image} alt={hotel.name} className="shopping-image" loading="lazy"
            onError={(e) => { e.target.style.display = "none"; }} />
        ) : (
          <div className="shopping-image-placeholder">No image</div>
        )}
        <div className="image-overlay" />
      </div>
      <div className="shopping-info">
        <h3 className="shopping-title" title={hotel.name}>
          {hotel.name} {hotel.hotel_class ? "★".repeat(Math.min(hotel.hotel_class, 5)) : ""}
        </h3>
        <div className="shopping-meta">
          {typeof hotel.rating === "number" ? (
            <span className="shopping-rating"><Star size={12} fill="#92400e" stroke="#92400e" /> {hotel.rating.toFixed(1)}</span>
          ) : (
            <span className="shopping-rating muted">New</span>
          )}
          {hotel.reviews ? <span className="shopping-reviews">({hotel.reviews.toLocaleString()})</span> : null}
          {hotel.address && <><span className="meta-dot">·</span><span className="ext-text">{hotel.address}</span></>}
        </div>
        {hotel.maps_link && (
          <div className="shopping-meta">
            <a
              href={hotel.maps_link}
              target="_blank"
              rel="noopener noreferrer"
              className="hotel-map-link"
              onClick={(e) => e.stopPropagation()}
            >
              <MapPin size={12} /> {hotel.address ? `View ${hotel.address} on map` : "View on map"}
            </a>
          </div>
        )}
        {(hotel.amenities || []).length > 0 && (
          <div className="shopping-meta">
            <span className="ext-text">{hotel.amenities.slice(0, 3).join(" · ")}</span>
          </div>
        )}
        <div className="shopping-price-row">
          {perNight ? (
            <><span className="shopping-price">{perNight}</span><span className="mrp-hint">/night</span></>
          ) : (
            <span className="price-unavailable">Price unavailable</span>
          )}
          {total && <span className="shopping-reviews">{total} total</span>}
        </div>
        {hotel.booking_link ? (
          <a href={hotel.booking_link} target="_blank" rel="noopener noreferrer" className="shopping-view-btn" onClick={(e) => e.stopPropagation()}>
            Book Hotel <ExternalLink size={14} />
          </a>
        ) : (
          <button className="shopping-view-btn" disabled>Book Hotel</button>
        )}
      </div>
    </div>
  );
}
