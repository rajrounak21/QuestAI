import { Star, Truck, ExternalLink } from 'lucide-react';
import { currencySymbol, currencyLocale } from '../api';

function formatPrice(price, currency) {
  if (!price || price === 0) return null;
  const symbol = currencySymbol(currency);
  // Indian grouping only for INR; en-US for the rest ($1,234,567 not $12,34,567)
  return `${symbol}${Math.round(price).toLocaleString(currencyLocale(currency))}`;
}

export default function ShoppingCard({ product }) {
  const hasRating = typeof product.rating === 'number';
  const hasStore = !!product.store;
  return (
    <div className="shopping-card">
      <div className="shopping-image-wrap">
        {product.tag && <span className="card-badge top-left">{product.tag}</span>}
        {hasRating && product.rating >= 4.3 && (
          <span className="card-badge top-right hot">
            <Star size={11} fill="white" stroke="white" /> Top Rated
          </span>
        )}
        {product.image_url ? (
          <img
            src={product.image_url}
            alt={product.title}
            className="shopping-image"
            loading="lazy"
            onError={(e) => { e.target.style.display = 'none'; }}
          />
        ) : (
          <div className="shopping-image-placeholder">No image</div>
        )}
        <div className="image-overlay" />
      </div>

      <div className="shopping-info">
        {hasStore && <p className="shopping-store"><span className="store-dot" />{product.store}</p>}
        <h3 className="shopping-title" title={product.title}>{product.title}</h3>

        <div className="shopping-meta">
          {hasRating ? (
            <span className="shopping-rating"><Star size={12} fill="#92400e" stroke="#92400e" /> {product.rating.toFixed(1)}</span>
          ) : (
            <span className="shopping-rating muted">New</span>
          )}
          {product.reviews ? <span className="shopping-reviews">({product.reviews.toLocaleString()})</span> : null}
          {product.extensions?.[0] && <span className="meta-dot">·</span>}
          {product.extensions?.[0] && <span className="ext-text">{product.extensions[0]}</span>}
        </div>

        <div className="shopping-price-row">
          {formatPrice(product.price, product.currency) ? (
            <>
              <span className="shopping-price">{formatPrice(product.price, product.currency)}</span>
              {product.tag && product.tag.toLowerCase().includes('off') && <span className="mrp-hint">{product.tag}</span>}
            </>
          ) : (
            <span className="price-unavailable">Price unavailable</span>
          )}
        </div>

        <div className="shopping-extras">
          {product.delivery ? (
            <span className="shopping-delivery"><Truck size={12} /> {product.delivery}</span>
          ) : (
            <span className="shopping-delivery muted">Free delivery on view</span>
          )}
        </div>

        {product.product_url ? (
          <a href={product.product_url} target="_blank" rel="noopener noreferrer" className="shopping-view-btn">
            View Product <ExternalLink size={14} />
          </a>
        ) : (
          <button className="shopping-view-btn" disabled>View Product</button>
        )}
      </div>
    </div>
  );
}
