import { useState, useMemo } from 'react';

export default function FlightFilters({ flights, filters, onFilterChange }) {
  const airlines = useMemo(() => {
    const set = new Set(flights.map((f) => f.airline));
    return Array.from(set).sort();
  }, [flights]);

  const priceRange = useMemo(() => {
    if (flights.length === 0) return { min: 0, max: 1000 };
    const prices = flights.map((f) => f.price);
    return { min: Math.floor(Math.min(...prices)), max: Math.ceil(Math.max(...prices)) };
  }, [flights]);

  const handleStopsChange = (value) => {
    onFilterChange({ ...filters, stops: value });
  };

  const handleAirlineToggle = (airline) => {
    const current = filters.airlines || [];
    const updated = current.includes(airline)
      ? current.filter((a) => a !== airline)
      : [...current, airline];
    onFilterChange({ ...filters, airlines: updated });
  };

  const handlePriceChange = (value) => {
    onFilterChange({ ...filters, maxPrice: value });
  };

  const handleDepartureChange = (value) => {
    onFilterChange({ ...filters, departureTime: value });
  };

  const handleSortChange = (value) => {
    onFilterChange({ ...filters, sortBy: value });
  };

  return (
    <div className="flight-filters">
      <h3>Filters</h3>

      <div className="filter-section">
        <h4>Sort By</h4>
        <select value={filters.sortBy || 'best'} onChange={(e) => handleSortChange(e.target.value)}>
          <option value="best">Best</option>
          <option value="cheapest">Cheapest</option>
          <option value="fastest">Fastest</option>
        </select>
      </div>

      <div className="filter-section">
        <h4>Stops</h4>
        <label className="filter-option">
          <input
            type="radio"
            name="stops"
            value="any"
            checked={!filters.stops || filters.stops === 'any'}
            onChange={() => handleStopsChange('any')}
          />
          Any
        </label>
        <label className="filter-option">
          <input
            type="radio"
            name="stops"
            value="0"
            checked={filters.stops === '0'}
            onChange={() => handleStopsChange('0')}
          />
          Non-stop
        </label>
        <label className="filter-option">
          <input
            type="radio"
            name="stops"
            value="1"
            checked={filters.stops === '1'}
            onChange={() => handleStopsChange('1')}
          />
          1 stop
        </label>
        <label className="filter-option">
          <input
            type="radio"
            name="stops"
            value="2+"
            checked={filters.stops === '2+'}
            onChange={() => handleStopsChange('2+')}
          />
          2+ stops
        </label>
      </div>

      <div className="filter-section">
        <h4>Airlines</h4>
        {airlines.map((airline) => (
          <label key={airline} className="filter-option">
            <input
              type="checkbox"
              checked={(filters.airlines || []).includes(airline)}
              onChange={() => handleAirlineToggle(airline)}
            />
            {airline}
          </label>
        ))}
      </div>

      <div className="filter-section">
        <h4>Max Price: ${filters.maxPrice || priceRange.max}</h4>
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
        <h4>Departure Time</h4>
        <label className="filter-option">
          <input
            type="radio"
            name="departure"
            value="any"
            checked={!filters.departureTime || filters.departureTime === 'any'}
            onChange={() => handleDepartureChange('any')}
          />
          Any
        </label>
        <label className="filter-option">
          <input
            type="radio"
            name="departure"
            value="morning"
            checked={filters.departureTime === 'morning'}
            onChange={() => handleDepartureChange('morning')}
          />
          Morning (6am-12pm)
        </label>
        <label className="filter-option">
          <input
            type="radio"
            name="departure"
            value="afternoon"
            checked={filters.departureTime === 'afternoon'}
            onChange={() => handleDepartureChange('afternoon')}
          />
          Afternoon (12pm-6pm)
        </label>
        <label className="filter-option">
          <input
            type="radio"
            name="departure"
            value="evening"
            checked={filters.departureTime === 'evening'}
            onChange={() => handleDepartureChange('evening')}
          />
          Evening (6pm-12am)
        </label>
        <label className="filter-option">
          <input
            type="radio"
            name="departure"
            value="night"
            checked={filters.departureTime === 'night'}
            onChange={() => handleDepartureChange('night')}
          />
          Night (12am-6am)
        </label>
      </div>
    </div>
  );
}
