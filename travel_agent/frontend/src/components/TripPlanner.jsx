import { useState, useRef, useEffect } from 'react';
import { planTrip, tripChat, deleteTrip } from '../api/trips';
import TripOverview from './TripOverview';
import TripItinerary from './TripItinerary';
import TripBudget from './TripBudget';
import SearchProgress from './SearchProgress';
import FlightDetails from './FlightDetails';
import HotelDetails from './HotelDetails';

export default function TripPlanner() {
  const [trip, setTrip] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [selectedFlight, setSelectedFlight] = useState(null);
  const [selectedHotel, setSelectedHotel] = useState(null);
  const [chatHistory, setChatHistory] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const chatEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory, loading]);

  const addMessage = (role, content, extra = {}) => {
    setChatHistory(prev => [...prev, { role, content, ...extra, id: Date.now() + Math.random() }]);
  };

  const handlePlanTrip = async (userQuery) => {
    if (!userQuery.trim()) return;

    addMessage('user', userQuery);
    setInputValue('');
    setLoading(true);
    setError(null);

    try {
      const result = await planTrip(userQuery, sessionId);

      if (result.error) {
        setError(result.error);
        addMessage('assistant', result.error, { isError: true });
      } else if (result.clarifying_questions && result.clarifying_questions.length > 0) {
        setSessionId(result.trip?.trip_id || sessionId);
        addMessage('assistant', result.message || 'I need a few more details:', {
          clarifying: result.clarifying_questions,
        });
      } else {
        setTrip(result.trip);
        setSessionId(result.trip?.trip_id || null);
        addMessage('assistant', result.message || `Trip to ${result.trip?.destination} is ready!`, {
          trip: result.trip,
        });
      }
    } catch (err) {
      console.error('Trip planning failed:', err);
      const msg = 'Trip planning is temporarily unavailable. Please try again.';
      setError(msg);
      addMessage('assistant', msg, { isError: true });
    } finally {
      setLoading(false);
    }
  };

  const handleAnswerQuestions = async (answers) => {
    const answerText = answers.join(', ');
    const lastUserMsg = chatHistory.findLast(m => m.role === 'user');
    const fullQuery = `${lastUserMsg?.content || ''}. ${answerText}`;

    addMessage('user', answerText);
    setLoading(true);
    setError(null);

    try {
      const result = await planTrip(fullQuery, sessionId);
      if (result.error) {
        setError(result.error);
        addMessage('assistant', result.error, { isError: true });
      } else if (result.clarifying_questions && result.clarifying_questions.length > 0) {
        addMessage('assistant', result.message || 'I need a few more details:', {
          clarifying: result.clarifying_questions,
        });
      } else {
        setTrip(result.trip);
        setSessionId(result.trip?.trip_id || null);
        addMessage('assistant', result.message || `Trip to ${result.trip?.destination} is ready!`, {
          trip: result.trip,
        });
      }
    } catch (err) {
      console.error('Trip planning failed:', err);
      const msg = 'Failed to process your answers. Please try again.';
      setError(msg);
      addMessage('assistant', msg, { isError: true });
    } finally {
      setLoading(false);
    }
  };

  const handleChat = async (message) => {
    if (!trip?.trip_id || !message.trim()) return;

    addMessage('user', message);
    setInputValue('');
    setLoading(true);
    setError(null);

    try {
      const result = await tripChat(trip.trip_id, message);
      if (result.error) {
        setError(result.error);
        addMessage('assistant', result.error, { isError: true });
      } else {
        setTrip(result.trip);
        addMessage('assistant', result.message || 'Done!', { trip: result.trip });
      }
    } catch (err) {
      console.error('Trip chat failed:', err);
      const msg = 'Failed to process your request. Please try again.';
      setError(msg);
      addMessage('assistant', msg, { isError: true });
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (loading) return;
    if (trip?.trip_id) {
      handleChat(inputValue);
    } else {
      handlePlanTrip(inputValue);
    }
  };

  const handleSelectFlight = (flight) => {
    if (!trip?.trip_id) return;
    setTrip({ ...trip, selected_flight: flight });
  };

  const handleSelectHotel = (hotel) => {
    if (!trip?.trip_id) return;
    setTrip({ ...trip, selected_hotel: hotel });
  };

  const handleNewTrip = async () => {
    if (trip?.trip_id) {
      try { await deleteTrip(trip.trip_id); } catch {}
    }
    setTrip(null);
    setSessionId(null);
    setSelectedFlight(null);
    setSelectedHotel(null);
    setChatHistory([]);
    setInputValue('');
    setError(null);
  };

  const quickActions = trip?.trip_id ? [
    "What's the total cost?",
    "Make it cheaper",
    "Change dates",
    "Upgrade hotel",
    "Nonstop flights",
    "Add more days",
  ] : null;

  return (
    <div className="trip-planner-chat">
      {chatHistory.length === 0 && !loading && (
        <div className="trip-input">
          <h2>Plan Your Trip</h2>
          <p>Describe your dream trip and I'll plan it for you</p>
          <div className="trip-input-form">
            <textarea
              placeholder="e.g., Plan a 5-day trip to Dubai from Delhi for 2 people, budget $2000"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              rows={3}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handlePlanTrip(inputValue);
                }
              }}
            />
            <button
              className="btn-primary"
              onClick={() => handlePlanTrip(inputValue)}
              disabled={!inputValue.trim()}
            >
              Plan Trip
            </button>
          </div>
          <div className="trip-examples">
            <p>Try:</p>
            <button onClick={() => handlePlanTrip("Plan a 5-day trip to Dubai from Delhi for 2 people, budget $2000")}>
              Dubai trip for 2
            </button>
            <button onClick={() => handlePlanTrip("Weekend getaway to Bali, 3 nights, budget $1500")}>
              Bali weekend
            </button>
            <button onClick={() => handlePlanTrip("7-day Japan trip from New York, 3 travelers, interested in food and culture")}>
              Japan food trip
            </button>
            <button onClick={() => handlePlanTrip("Plan a trip to Paris")}>
              Paris (incomplete)
            </button>
          </div>
        </div>
      )}

      {chatHistory.length > 0 && (
        <div className="chat-container">
          <div className="chat-messages">
            {chatHistory.map((msg) => (
              <ChatMessage
                key={msg.id}
                msg={msg}
                onAnswerQuestions={handleAnswerQuestions}
                onSelectFlight={setSelectedFlight}
                onSelectHotel={setSelectedHotel}
              />
            ))}

            {loading && (
              <div className="chat-message assistant">
                <div className="message-avatar">🤖</div>
                <div className="message-content">
                  <SearchProgress loading={loading} searchType="trips" />
                </div>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>

          {trip?.trip_id && !loading && (
            <div className="quick-actions">
              {quickActions.map((action, i) => (
                <button
                  key={i}
                  className="quick-action-btn"
                  onClick={() => handleChat(action)}
                >
                  {action}
                </button>
              ))}
            </div>
          )}

          {trip?.trip_id && (
            <div className="trip-header-bar">
              <span className="trip-dest">{trip.destination}</span>
              <button className="btn-secondary btn-sm" onClick={handleNewTrip}>New Trip</button>
            </div>
          )}

          <form className="chat-input-bar" onSubmit={handleSubmit}>
            <input
              ref={inputRef}
              type="text"
              className="chat-input"
              placeholder={trip?.trip_id ? "Ask about your trip..." : "Describe your trip..."}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              disabled={loading}
            />
            <button type="submit" className="chat-send-btn" disabled={loading || !inputValue.trim()}>
              {loading ? '...' : '→'}
            </button>
          </form>
        </div>
      )}

      {selectedFlight && (
        <FlightDetails flight={selectedFlight} onClose={() => setSelectedFlight(null)} />
      )}
      {selectedHotel && (
        <HotelDetails hotel={selectedHotel} onClose={() => setSelectedHotel(null)} />
      )}
    </div>
  );
}


function ChatMessage({ msg, onAnswerQuestions, onSelectFlight, onSelectHotel }) {
  const [showTrip, setShowTrip] = useState(true);

  if (msg.role === 'user') {
    return (
      <div className="chat-message user">
        <div className="message-content user-bubble">
          {msg.content}
        </div>
      </div>
    );
  }

  return (
    <div className="chat-message assistant">
      <div className="message-avatar">🤖</div>
      <div className="message-content assistant-bubble">
        <p>{msg.content}</p>

        {msg.clarifying && (
          <ClarifyingQuestionsInline
            questions={msg.clarifying}
            onAnswer={onAnswerQuestions}
          />
        )}

        {msg.trip && showTrip && (
          <div className="trip-result-inline">
            <TripOverview
              trip={msg.trip}
              onSelectFlight={() => {}}
              onSelectHotel={() => {}}
              onViewFlight={onSelectFlight}
              onViewHotel={onSelectHotel}
            />
            <TripBudget trip={msg.trip} />
            <TripItinerary trip={msg.trip} />
          </div>
        )}
      </div>
    </div>
  );
}


function ClarifyingQuestionsInline({ questions, onAnswer }) {
  const [answers, setAnswers] = useState({});

  const handleSelect = (field, value) => {
    setAnswers(prev => ({ ...prev, [field]: value }));
  };

  const handleSubmit = () => {
    const answerList = questions.map(q => {
      const answer = answers[q.field];
      if (answer) return `${q.field}: ${answer}`;
      return null;
    }).filter(Boolean);
    onAnswer(answerList);
  };

  const allAnswered = questions.every(q => {
    if (answers[q.field]) return true;
    if (answers[q.field + '_custom'] && answers[q.field + '_manual']) return true;
    if (answers[q.field + '_custom'] && answers[q.field] !== undefined && answers[q.field] !== '') return true;
    return false;
  });

  return (
    <div className="clarifying-inline">
      {questions.map((q, idx) => (
        <div key={idx} className="clarifying-question">
          <div className="question-text">{q.question}</div>

          {q.options ? (
            <div>
              <div className="question-options">
                {q.options.map((opt, optIdx) => (
                  <button
                    key={optIdx}
                    className={`option-btn ${answers[q.field] === opt || (opt === 'Other' && answers[q.field + '_custom']) ? 'selected' : ''}`}
                    onClick={() => {
                      if (opt === 'Other') {
                        setAnswers(prev => ({ ...prev, [q.field]: '', [q.field + '_custom']: true }));
                      } else {
                        setAnswers(prev => ({ ...prev, [q.field]: opt, [q.field + '_custom']: false }));
                      }
                    }}
                  >
                    {opt}
                  </button>
                ))}
              </div>
              {answers[q.field + '_custom'] && (
                <input
                  type="text"
                  className="question-input"
                  placeholder={`Enter your ${q.field}...`}
                  autoFocus
                  value={answers[q.field] || ''}
                  onChange={(e) => handleSelect(q.field, e.target.value)}
                />
              )}
            </div>
          ) : null}

          {q.field === 'budget' && (
            <div className="budget-manual">
              <span className="or-divider">or enter amount</span>
              <div className="budget-input-row">
                <span className="currency-symbol">$</span>
                <input
                  type="number"
                  className="question-input budget-input"
                  placeholder="e.g. 3000"
                  value={answers[q.field + '_manual'] || ''}
                  onChange={(e) => {
                    const val = e.target.value;
                    setAnswers(prev => ({
                      ...prev,
                      [q.field + '_manual']: val,
                      [q.field]: val ? `$${val} custom budget` : prev[q.field],
                    }));
                  }}
                />
              </div>
            </div>
          )}

          {!q.options && q.field !== 'budget' && q.field !== 'departure_date' && q.field !== 'return_date' && (
            <input
              type="text"
              className="question-input"
              placeholder={`Enter ${q.field}...`}
              value={answers[q.field] || ''}
              onChange={(e) => handleSelect(q.field, e.target.value)}
            />
          )}

          {(q.field === 'departure_date' || q.field === 'return_date') && (
            <div className="date-picker-row">
              <input
                type="date"
                className="question-input date-input"
                value={answers[q.field] || ''}
                onChange={(e) => handleSelect(q.field, e.target.value)}
              />
            </div>
          )}
        </div>
      ))}

      <button
        className="btn-primary btn-sm"
        onClick={handleSubmit}
        disabled={!allAnswered}
      >
        Continue
      </button>
    </div>
  );
}
