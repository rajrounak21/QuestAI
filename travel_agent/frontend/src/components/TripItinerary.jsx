export default function TripItinerary({ trip }) {
  const formatActivityTime = (time) => {
    if (!time) return '';
    const [hours, minutes] = time.split(':');
    const h = parseInt(hours);
    const ampm = h >= 12 ? 'PM' : 'AM';
    const h12 = h % 12 || 12;
    return `${h12}:${minutes} ${ampm}`;
  };

  if (!trip.itinerary || trip.itinerary.length === 0) {
    return (
      <div className="trip-itinerary">
        <h3>📅 Itinerary</h3>
        <div className="itinerary-empty">
          <p>No day-by-day itinerary available yet.</p>
          <p className="itinerary-empty-hint">Try asking: "Create a detailed itinerary for my trip"</p>
        </div>
      </div>
    );
  }

  return (
    <div className="trip-itinerary">
      <h3>📅 Itinerary</h3>
      {trip.itinerary.map((day) => (
        <div key={day.day} className="itinerary-day">
          <div className="day-header">
            <span className="day-number">Day {day.day}</span>
            {day.title && <span className="day-title">{day.title}</span>}
          </div>
          <div className="day-activities">
            {day.activities?.map((activity, idx) => (
              <div key={idx} className="activity">
                <div className="activity-time">
                  {formatActivityTime(activity.time)}
                </div>
                <div className="activity-content">
                  <div className="activity-name">{activity.name}</div>
                  {activity.description && (
                    <div className="activity-description">{activity.description}</div>
                  )}
                  <div className="activity-meta">
                    {activity.location && (
                      <span className="activity-location">📍 {activity.location}</span>
                    )}
                    {activity.estimated_cost > 0 && (
                      <span className="activity-cost">~${activity.estimated_cost}</span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
