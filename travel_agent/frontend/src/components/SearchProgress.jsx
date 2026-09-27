import { useState, useEffect } from 'react';

const FLIGHT_STEPS = [
  { text: 'Understanding your request', delay: 500 },
  { text: 'Finding airports', delay: 1000 },
  { text: 'Searching Google Flights', delay: 1500 },
  { text: 'Comparing available options', delay: 2500 },
];

const HOTEL_STEPS = [
  { text: 'Understanding your request', delay: 500 },
  { text: 'Finding hotels', delay: 1000 },
  { text: 'Checking availability', delay: 1500 },
  { text: 'Comparing available hotels', delay: 2500 },
];

const TRIP_STEPS = [
  { text: 'Understanding your trip request', delay: 500 },
  { text: 'Searching flights', delay: 1500 },
  { text: 'Searching hotels', delay: 2500 },
  { text: 'Researching destination', delay: 3500 },
  { text: 'Building your itinerary', delay: 4500 },
];

export default function SearchProgress({ loading, searchType }) {
  const [visibleSteps, setVisibleSteps] = useState([]);

  const steps = searchType === 'hotels' ? HOTEL_STEPS : searchType === 'trips' ? TRIP_STEPS : FLIGHT_STEPS;
  const label = searchType === 'hotels' ? 'Searching hotels' : searchType === 'trips' ? 'Planning your trip' : 'Searching flights';

  useEffect(() => {
    if (!loading) {
      setVisibleSteps([]);
      return;
    }

    setVisibleSteps([]);

    const timers = steps.map((step, index) =>
      setTimeout(() => {
        setVisibleSteps((prev) => [...prev, step.text]);
      }, step.delay)
    );

    return () => timers.forEach(clearTimeout);
  }, [loading, searchType]);

  if (!loading) return null;

  return (
    <div className="search-progress">
      <div className="progress-header">
        <span className="spinner"></span>
        <span>{label}</span>
      </div>
      <div className="progress-steps">
        {visibleSteps.map((step, index) => (
          <div key={index} className="progress-step">
            <span className="check">✓</span>
            <span>{step}</span>
          </div>
        ))}
        {visibleSteps.length < steps.length && (
          <div className="progress-step active">
            <span className="spinner-small"></span>
            <span>Processing...</span>
          </div>
        )}
      </div>
    </div>
  );
}
