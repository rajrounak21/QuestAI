export default function EmptyState({ error, followUp }) {
  if (error) {
    return (
      <div className="empty-state error">
        <div className="empty-icon">⚠️</div>
        <h3>Something went wrong</h3>
        <p>{error}</p>
      </div>
    );
  }

  if (followUp) {
    return (
      <div className="empty-state follow-up">
        <div className="empty-icon">💬</div>
        <h3>I need more information</h3>
        <p>{followUp}</p>
      </div>
    );
  }

  return (
    <div className="empty-state">
      <div className="empty-icon">✈️</div>
      <h3>No flights found</h3>
      <p>Try changing your date or destination.</p>
    </div>
  );
}
