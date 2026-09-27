import { useState } from 'react';

export default function FlightSearch({ onSearch, loading }) {
  const [mode, setMode] = useState('form');
  const [nlQuery, setNlQuery] = useState('');
  const [form, setForm] = useState({
    origin: '',
    destination: '',
    departureDate: '',
    returnDate: '',
    passengers: 1,
    cabinClass: 'economy',
  });

  const handleFormSubmit = (e) => {
    e.preventDefault();
    let query = `Find flights from ${form.origin} to ${form.destination} on ${form.departureDate}`;
    if (form.returnDate) {
      query += ` returning ${form.returnDate}`;
    }
    if (form.passengers > 1) {
      query += ` for ${form.passengers} passengers`;
    }
    if (form.cabinClass !== 'economy') {
      query += ` in ${form.cabinClass}`;
    }
    onSearch(query);
  };

  const handleNlSubmit = (e) => {
    e.preventDefault();
    if (nlQuery.trim()) {
      onSearch(nlQuery.trim());
    }
  };

  return (
    <div className="flight-search">
      <div className="search-header">
        <h2>Flight Search</h2>
        <div className="mode-toggle">
          <button
            className={mode === 'form' ? 'active' : ''}
            onClick={() => setMode('form')}
          >
            Form
          </button>
          <button
            className={mode === 'nl' ? 'active' : ''}
            onClick={() => setMode('nl')}
          >
            Natural Language
          </button>
        </div>
      </div>

      {mode === 'form' ? (
        <form onSubmit={handleFormSubmit} className="search-form">
          <div className="form-row">
            <div className="form-group">
              <label>From</label>
              <input
                type="text"
                placeholder="City or airport (e.g., Delhi)"
                value={form.origin}
                onChange={(e) => setForm({ ...form, origin: e.target.value })}
                required
              />
            </div>
            <div className="form-group">
              <label>To</label>
              <input
                type="text"
                placeholder="City or airport (e.g., Dubai)"
                value={form.destination}
                onChange={(e) => setForm({ ...form, destination: e.target.value })}
                required
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Departure</label>
              <input
                type="date"
                value={form.departureDate}
                onChange={(e) => setForm({ ...form, departureDate: e.target.value })}
                required
              />
            </div>
            <div className="form-group">
              <label>Return (optional)</label>
              <input
                type="date"
                value={form.returnDate}
                onChange={(e) => setForm({ ...form, returnDate: e.target.value })}
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Passengers</label>
              <input
                type="number"
                min="1"
                max="9"
                value={form.passengers}
                onChange={(e) => setForm({ ...form, passengers: parseInt(e.target.value) || 1 })}
              />
            </div>
            <div className="form-group">
              <label>Class</label>
              <select
                value={form.cabinClass}
                onChange={(e) => setForm({ ...form, cabinClass: e.target.value })}
              >
                <option value="economy">Economy</option>
                <option value="premium_economy">Premium Economy</option>
                <option value="business">Business</option>
                <option value="first">First</option>
              </select>
            </div>
          </div>

          <button type="submit" className="search-btn" disabled={loading}>
            {loading ? 'Searching...' : 'Search Flights'}
          </button>
        </form>
      ) : (
        <form onSubmit={handleNlSubmit} className="nl-form">
          <textarea
            placeholder="Find me flights from Delhi to Dubai on October 15..."
            value={nlQuery}
            onChange={(e) => setNlQuery(e.target.value)}
            rows={3}
          />
          <button type="submit" className="search-btn" disabled={loading || !nlQuery.trim()}>
            {loading ? 'Searching...' : 'Search Flights'}
          </button>
        </form>
      )}
    </div>
  );
}
