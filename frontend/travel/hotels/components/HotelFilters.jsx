import { useMemo } from "react";
import { currencySymbol } from "../api";

export default function HotelFilters({ hotels, filters, onFilterChange, priceBounds }) {
  const amenities = useMemo(() => {
    const counts = {};
    (hotels || []).forEach((h) => {
      (h.amenities || []).forEach((a) => { counts[a] = (counts[a] || 0) + 1; });
    });
    return Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([n]) => n);
  }, [hotels]);

  const cur = useMemo(
    () => (hotels || []).find((h) => h.currency)?.currency || "USD",
    [hotels]
  );

  return (
    <div>
      <div className="filter-group">
        <h4>Min rating</h4>
        {["any", "3.5", "4.0", "4.5"].map((v) => (
          <label key={v} className="filter-check">
            <input
              type="radio"
              name="ht-rating"
              checked={String(filters.minRating || "any") === v}
              onChange={() => onFilterChange({ ...filters, minRating: v })}
            />
            {v === "any" ? "Any" : `${v}+`}
          </label>
        ))}
      </div>
      <div className="filter-group">
        <h4>Max price/night ({currencySymbol(cur)}{priceBounds.max.toLocaleString()})</h4>
        <input
          type="range"
          min={priceBounds.min}
          max={priceBounds.max}
          value={filters.maxPrice ?? priceBounds.max}
          onChange={(e) => onFilterChange({ ...filters, maxPrice: parseInt(e.target.value) })}
          className="filter-range"
        />
      </div>
      {amenities.length > 0 && (
        <div className="filter-group">
          <h4>Amenities</h4>
          {amenities.map((a) => (
            <label key={a} className="filter-check">
              <input
                type="checkbox"
                checked={(filters.amenities || []).includes(a)}
                onChange={() => {
                  const curSel = filters.amenities || [];
                  onFilterChange({
                    ...filters,
                    amenities: curSel.includes(a) ? curSel.filter((x) => x !== a) : [...curSel, a],
                  });
                }}
              />
              {a}
            </label>
          ))}
        </div>
      )}
      <div className="filter-group">
        <label className="filter-check">
          <input
            type="checkbox"
            checked={!!filters.freeCancellation}
            onChange={(e) => onFilterChange({ ...filters, freeCancellation: e.target.checked })}
          />
          Free cancellation only
        </label>
      </div>
    </div>
  );
}
