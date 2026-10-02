import { useMemo } from "react";
import { currencySymbol } from "../api";

export default function FlightFilters({ flights, filters, onFilterChange, priceBounds }) {
  const airlines = useMemo(() => {
    const set = new Set((flights || []).map((f) => f.airline).filter(Boolean));
    return Array.from(set).sort();
  }, [flights]);

  const cur = useMemo(
    () => (flights || []).find((f) => f.currency)?.currency || "USD",
    [flights]
  );

  return (
    <div>
      <div className="filter-group">
        <h4>Stops</h4>
        {["any", "0", "1", "2+"].map((v) => (
          <label key={v} className="filter-check">
            <input
              type="radio"
              name="fl-stops"
              checked={(filters.stops || "any") === v}
              onChange={() => onFilterChange({ ...filters, stops: v })}
            />
            {v === "any" ? "Any" : v === "0" ? "Non-stop" : v === "1" ? "1 stop" : "2+ stops"}
          </label>
        ))}
      </div>
      <div className="filter-group">
        <h4>Airlines</h4>
        {airlines.length === 0 && <p className="filter-empty">No airlines yet</p>}
        {airlines.map((a) => (
          <label key={a} className="filter-check">
            <input
              type="checkbox"
              checked={(filters.airlines || []).includes(a)}
              onChange={() => {
                const curSel = filters.airlines || [];
                onFilterChange({
                  ...filters,
                  airlines: curSel.includes(a) ? curSel.filter((x) => x !== a) : [...curSel, a],
                });
              }}
            />
            {a}
          </label>
        ))}
      </div>
      <div className="filter-group">
        <h4>Max price ({currencySymbol(cur)}{priceBounds.max.toLocaleString()})</h4>
        <input
          type="range"
          min={priceBounds.min}
          max={priceBounds.max}
          value={filters.maxPrice ?? priceBounds.max}
          onChange={(e) => onFilterChange({ ...filters, maxPrice: parseInt(e.target.value) })}
          className="filter-range"
        />
      </div>
    </div>
  );
}
