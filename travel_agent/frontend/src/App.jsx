import { useState, useMemo } from 'react';
import FlightSearch from './components/FlightSearch';
import FlightCard from './components/FlightCard';
import FlightFilters from './components/FlightFilters';
import FlightDetails from './components/FlightDetails';
import HotelSearch from './components/HotelSearch';
import HotelCard from './components/HotelCard';
import HotelFilters from './components/HotelFilters';
import HotelDetails from './components/HotelDetails';
import TripPlanner from './components/TripPlanner';
import SearchProgress from './components/SearchProgress';
import EmptyState from './components/EmptyState';
import { searchFlights } from './api/flights';
import { searchHotels } from './api/hotels';
import './App.css';

function App() {
  const [searchType, setSearchType] = useState('flights');
  const [flights, setFlights] = useState([]);
  const [hotels, setHotels] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [followUp, setFollowUp] = useState(null);
  const [selectedItem, setSelectedItem] = useState(null);
  const [flightFilters, setFlightFilters] = useState({ sortBy: 'best' });
  const [hotelFilters, setHotelFilters] = useState({ sortBy: 'relevance' });
  const [hasSearched, setHasSearched] = useState(false);

  const handleFlightSearch = async (query) => {
    setLoading(true);
    setError(null);
    setFollowUp(null);
    setFlights([]);
    setHasSearched(true);
    setSelectedItem(null);

    try {
      const result = await searchFlights(query);
      if (result.error) {
        setError(result.error);
      } else if (result.follow_up_question) {
        setFollowUp(result.follow_up_question);
      } else {
        setFlights(result.flights || []);
      }
    } catch (err) {
      console.error('Flight search failed:', err);
      setError('Flight search is temporarily unavailable. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleHotelSearch = async (query) => {
    setLoading(true);
    setError(null);
    setFollowUp(null);
    setHotels([]);
    setHasSearched(true);
    setSelectedItem(null);

    try {
      const result = await searchHotels(query);
      if (result.error) {
        setError(result.error);
      } else if (result.follow_up_question) {
        setFollowUp(result.follow_up_question);
      } else {
        setHotels(result.hotels || []);
      }
    } catch (err) {
      console.error('Hotel search failed:', err);
      setError('Hotel search is temporarily unavailable. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const filteredFlights = useMemo(() => {
    let result = [...flights];

    if (flightFilters.stops && flightFilters.stops !== 'any') {
      if (flightFilters.stops === '2+') {
        result = result.filter((f) => f.stops >= 2);
      } else {
        result = result.filter((f) => f.stops === parseInt(flightFilters.stops));
      }
    }

    if (flightFilters.airlines && flightFilters.airlines.length > 0) {
      result = result.filter((f) => flightFilters.airlines.includes(f.airline));
    }

    if (flightFilters.maxPrice) {
      result = result.filter((f) => f.price <= flightFilters.maxPrice);
    }

    if (flightFilters.departureTime && flightFilters.departureTime !== 'any') {
      result = result.filter((f) => {
        const time = f.departure.time;
        if (!time) return true;
        const hour = parseInt(time.split(' ')[1]?.split(':')[0] || '0');
        switch (flightFilters.departureTime) {
          case 'morning': return hour >= 6 && hour < 12;
          case 'afternoon': return hour >= 12 && hour < 18;
          case 'evening': return hour >= 18 && hour < 24;
          case 'night': return hour >= 0 && hour < 6;
          default: return true;
        }
      });
    }

    switch (flightFilters.sortBy) {
      case 'cheapest':
        result.sort((a, b) => a.price - b.price);
        break;
      case 'fastest':
        result.sort((a, b) => a.duration - b.duration);
        break;
      default:
        break;
    }

    return result;
  }, [flights, flightFilters]);

  const filteredHotels = useMemo(() => {
    let result = [...hotels];

    if (hotelFilters.minRating && hotelFilters.minRating !== 'any') {
      const min = parseFloat(hotelFilters.minRating);
      result = result.filter((h) => h.rating && h.rating >= min);
    }

    if (hotelFilters.hotelClass && hotelFilters.hotelClass !== 'any') {
      const cls = parseInt(hotelFilters.hotelClass);
      result = result.filter((h) => h.hotel_class === cls);
    }

    if (hotelFilters.maxPrice) {
      result = result.filter((h) => h.price_per_night <= hotelFilters.maxPrice);
    }

    if (hotelFilters.amenities && hotelFilters.amenities.length > 0) {
      result = result.filter((h) =>
        hotelFilters.amenities.every((a) => h.amenities.includes(a))
      );
    }

    if (hotelFilters.freeCancellation) {
      result = result.filter((h) => h.free_cancellation);
    }

    switch (hotelFilters.sortBy) {
      case 'price':
        result.sort((a, b) => a.price_per_night - b.price_per_night);
        break;
      case 'rating':
        result.sort((a, b) => (b.rating || 0) - (a.rating || 0));
        break;
      case 'reviews':
        result.sort((a, b) => (b.reviews || 0) - (a.reviews || 0));
        break;
      default:
        break;
    }

    return result;
  }, [hotels, hotelFilters]);

  const currentResults = searchType === 'flights' ? filteredFlights : filteredHotels;
  const resultCount = currentResults.length;
  const resultLabel = searchType === 'flights' ? 'flight' : 'hotel';

  return (
    <div className="app">
      <header className="app-header">
        <h1>QuestAI Travel</h1>
        <div className="search-type-toggle">
          <button
            className={searchType === 'flights' ? 'active' : ''}
            onClick={() => { setSearchType('flights'); setHasSearched(false); setError(null); setFollowUp(null); }}
          >
            ✈️ Flights
          </button>
          <button
            className={searchType === 'hotels' ? 'active' : ''}
            onClick={() => { setSearchType('hotels'); setHasSearched(false); setError(null); setFollowUp(null); }}
          >
            🏨 Hotels
          </button>
          <button
            className={searchType === 'trips' ? 'active' : ''}
            onClick={() => { setSearchType('trips'); setHasSearched(false); setError(null); setFollowUp(null); }}
          >
            🗺️ Trip Planner
          </button>
        </div>
      </header>

      <main className="app-main">
        {searchType === 'trips' ? (
          <TripPlanner />
        ) : (
          <>
            {searchType === 'flights' ? (
              <FlightSearch onSearch={handleFlightSearch} loading={loading} />
            ) : (
              <HotelSearch onSearch={handleHotelSearch} loading={loading} />
            )}

            <SearchProgress loading={loading} searchType={searchType} />

            {error && <EmptyState error={error} />}
            {followUp && <EmptyState followUp={followUp} />}

            {!loading && !error && !followUp && hasSearched && resultCount === 0 && (
              <EmptyState />
            )}

            {!loading && resultCount > 0 && (
              <div className="results-container">
                <div className="results-sidebar">
                  {searchType === 'flights' ? (
                    <FlightFilters
                      flights={flights}
                      filters={flightFilters}
                      onFilterChange={setFlightFilters}
                    />
                  ) : (
                    <HotelFilters
                      hotels={hotels}
                      filters={hotelFilters}
                      onFilterChange={setHotelFilters}
                    />
                  )}
                </div>
                <div className="results-main">
                  <div className="results-count">
                    Found {resultCount} {resultLabel} options
                  </div>
                  <div className="results-list">
                    {searchType === 'flights' ? (
                      filteredFlights.map((flight) => (
                        <FlightCard
                          key={flight.id}
                          flight={flight}
                          onSelect={setSelectedItem}
                        />
                      ))
                    ) : (
                      filteredHotels.map((hotel) => (
                        <HotelCard
                          key={hotel.id}
                          hotel={hotel}
                          onSelect={setSelectedItem}
                        />
                      ))
                    )}
                  </div>
                  {resultCount === 0 && (
                    <div className="no-results">
                      No {resultLabel}s match your filters. Try adjusting your criteria.
                    </div>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </main>

      {selectedItem && searchType === 'flights' && (
        <FlightDetails
          flight={selectedItem}
          onClose={() => setSelectedItem(null)}
        />
      )}

      {selectedItem && searchType === 'hotels' && (
        <HotelDetails
          hotel={selectedItem}
          onClose={() => setSelectedItem(null)}
        />
      )}
    </div>
  );
}

export default App;
