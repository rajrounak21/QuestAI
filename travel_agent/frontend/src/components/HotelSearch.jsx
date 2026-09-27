import { useState } from 'react';

export default function HotelSearch({ onSearch, loading }) {
  const [mode, setMode] = useState('form');
  const [nlQuery, setNlQuery] = useState('');
  const [form, setForm] = useState({
    location: '',
    checkIn: '',
    checkOut: '',
    guests: 2,
    rooms: 1,
  });

  const handleFormSubmit = (e) => {
    e.preventDefault();
    let query = `Find hotels in ${form.location} from ${form.checkIn} to ${form.checkOut}`;
    if (form.guests > 1) {
      query += ` for ${form.guests} people`;
    }
    if (form.rooms > 1) {
      query += `, ${form.rooms} rooms`;
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
    <div className="hotel-search">
      <div className="search-header">
        <h2>Hotel Search</h2>
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
          <div className="form-group full-width">
            <label>Location</label>
            <input
              type="text"
              placeholder="City or hotel (e.g., Dubai, Bali Resorts)"
              value={form.location}
              onChange={(e) => setForm({ ...form, location: e.target.value })}
              required
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Check-in</label>
              <input
                type="date"
                value={form.checkIn}
                onChange={(e) => setForm({ ...form, checkIn: e.target.value })}
                required
              />
            </div>
            <div className="form-group">
              <label>Check-out</label>
              <input
                type="date"
                value={form.checkOut}
                onChange={(e) => setForm({ ...form, checkOut: e.target.value })}
                required
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Guests</label>
              <input
                type="number"
                min="1"
                max="10"
                value={form.guests}
                onChange={(e) => setForm({ ...form, guests: parseInt(e.target.value) || 1 })}
              />
            </div>
            <div className="form-group">
              <label>Rooms</label>
              <input
                type="number"
                min="1"
                max="5"
                value={form.rooms}
                onChange={(e) => setForm({ ...form, rooms: parseInt(e.target.value) || 1 })}
              />
            </div>
          </div>

          <button type="submit" className="search-btn" disabled={loading}>
            {loading ? 'Searching...' : 'Search Hotels'}
          </button>
        </form>
      ) : (
        <form onSubmit={handleNlSubmit} className="nl-form">
          <textarea
            placeholder="Find hotels in Dubai for October 15-20 for 2 people..."
            value={nlQuery}
            onChange={(e) => setNlQuery(e.target.value)}
            rows={3}
          />
          <button type="submit" className="search-btn" disabled={loading || !nlQuery.trim()}>
            {loading ? 'Searching...' : 'Search Hotels'}
          </button>
        </form>
      )}
    </div>
  );
}
