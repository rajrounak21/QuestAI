import { useState } from 'react';

export default function TripChat({ trip, onChat, loading }) {
  const [message, setMessage] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (message.trim() && !loading) {
      onChat(message.trim());
      setMessage('');
    }
  };

  const quickActions = [
    { label: "Make it cheaper", message: "Make the trip cheaper" },
    { label: "Change dates", message: "Change the dates to next month" },
    { label: "Upgrade hotel", message: "Change to a 5-star hotel" },
    { label: "Nonstop flights", message: "Find nonstop flights" },
    { label: "Add more days", message: "Add 2 more days to the trip" },
    { label: "What's the total?", message: "What is my total cost?" },
  ];

  return (
    <div className="trip-chat">
      <h3>💬 Modify Your Trip</h3>
      <div className="chat-input">
        <form onSubmit={handleSubmit}>
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="e.g., Make it cheaper, Change dates to 20th..."
            disabled={loading}
          />
          <button type="submit" disabled={loading || !message.trim()}>
            {loading ? '...' : '→'}
          </button>
        </form>
      </div>

      <div className="quick-actions">
        {quickActions.map((action) => (
          <button
            key={action.label}
            className="quick-action"
            onClick={() => onChat(action.message)}
            disabled={loading}
          >
            {action.label}
          </button>
        ))}
      </div>

      {trip.conversation && trip.conversation.length > 0 && (
        <div className="chat-history">
          {trip.conversation.slice(-3).map((exchange, idx) => (
            <div key={idx} className="chat-exchange">
              <div className="chat-user">{exchange.user}</div>
              <div className="chat-assistant">{exchange.assistant}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
