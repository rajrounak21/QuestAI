import { useMemo } from 'react';

export default function HotelFilters({ hotels, filters, onFilterChange }) {
  const priceRange = useMemo(() => {
    if (hotels.length === 0) return { min: 0, max: 1000 };
    const prices = hotels.map((h) => h.price_per_night).filter((p) => p > 0);
    return { min: Math.floor(Math.min(...prices)), max: Math.ceil(Math.max(...prices)) };
  }, [hotels]);

  const allAmenities = useMemo(() => {
    const counts = {};
    hotels.forEach((h) => {
      (h.amenities || []).forEach((a) => {
        counts[a] = (counts[a] || 0) + 1;
      });
    });
    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([name]) => name);
  }, [hotels]);

  const handleSortChange = (value) => {
    onFilterChange({ ...filters, sortBy: value });
  };

  const handleRatingChange = (value) => {
    onFilterChange({ ...filters, minRating: value });
  };

  const handleClassChange = (value) => {
    onFilterChange({ ...filters, hotelClass: value });
  };

  const handlePriceChange = (value) => {
    onFilterChange({ ...filters, maxPrice: value });
  };

  const handleAmenityToggle = (amenity) => {
    const current = filters.amenities || [];
    const updated = current.includes(amenity)
      ? current.filter((a) => a !== amenity)
      : [...current, amenity];
    onFilterChange({ ...filters, amenities: updated });
  };

  const handleCancelChange = (value) => {
    onFilterChange({ ...filters, freeCancellation: value });
  };

  return (
    <div className="hotel-filters">
      <h3>Filters</h3>

      <div className="filter-section">
        <h4>Sort By</h4>
        <select value={filters.sortBy || 'relevance'} onChange={(e) => handleSortChange(e.target.value)}>
          <option value="relevance">Recommended</option>
          <option value="price">Price (Low to High)</option>
          <option value="rating">Rating (High to Low)</option>
          <option value="reviews">Most Reviewed</option>
        </select>
      </div>

      <div className="filter-section">
        <h4>Rating</h4>
        <label className="filter-option">
          <input
            type="radio"
            name="rating"
            value="any"
            checked={!filters.minRating || filters.minRating === 'any'}
            onChange={() => handleRatingChange('any')}
          />
          Any
        </label>
        <label className="filter-option">
          <input
            type="radio"
            name="rating"
            value="4"
            checked={filters.minRating === '4'}
            onChange={() => handleRatingChange('4')}
          />
          ★ 4+
        </label>
        <label className="filter-option">
          <input
            type="radio"
            name="rating"
            value="4.5"
            checked={filters.minRating === '4.5'}
            onChange={() => handleRatingChange('4.5')}
          />
          ★ 4.5+
        </label>
      </div>

      <div className="filter-section">
        <h4>Hotel Class</h4>
        <label className="filter-option">
          <input
            type="radio"
            name="class"
            value="any"
            checked={!filters.hotelClass || filters.hotelClass === 'any'}
            onChange={() => handleClassChange('any')}
          />
          Any
        </label>
        <label className="filter-option">
          <input
            type="radio"
            name="class"
            value="3"
            checked={filters.hotelClass === '3'}
            onChange={() => handleClassChange('3')}
          />
          ★★★
        </label>
        <label className="filter-option">
          <input
            type="radio"
            name="class"
            value="4"
            checked={filters.hotelClass === '4'}
            onChange={() => handleClassChange('4')}
          />
          ★★★★
        </label>
        <label className="filter-option">
          <input
            type="radio"
            name="class"
            value="5"
            checked={filters.hotelClass === '5'}
            onChange={() => handleClassChange('5')}
          />
          ★★★★★
        </label>
      </div>

      <div className="filter-section">
        <h4>Max Price: ${filters.maxPrice || priceRange.max} /night</h4>
        <input
          type="range"
          min={priceRange.min}
          max={priceRange.max}
          value={filters.maxPrice || priceRange.max}
          onChange={(e) => handlePriceChange(parseInt(e.target.value))}
        />
        <div className="range-labels">
          <span>${priceRange.min}</span>
          <span>${priceRange.max}</span>
        </div>
      </div>

      <div className="filter-section">
        <h4>Amenities</h4>
        {allAmenities.map((amenity) => (
          <label key={amenity} className="filter-option">
            <input
              type="checkbox"
              checked={(filters.amenities || []).includes(amenity)}
              onChange={() => handleAmenityToggle(amenity)}
            />
            {amenity}
          </label>
        ))}
      </div>

      <div className="filter-section">
        <label className="filter-option">
          <input
            type="checkbox"
            checked={filters.freeCancellation || false}
            onChange={(e) => handleCancelChange(e.target.checked)}
          />
          Free Cancellation
        </label>
      </div>
    </div>
  );
}
