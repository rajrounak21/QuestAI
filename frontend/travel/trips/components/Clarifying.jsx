import { useState } from "react";
import { Send } from "lucide-react";

// Renders the graph's clarifying questions: option chips + free text per
// question, one "Send answers" submit joining "field: value" lines.
export default function Clarifying({ questions, message, loading, onAnswer }) {
  const [answers, setAnswers] = useState({});

  const set = (field, value) => setAnswers((cur) => ({ ...cur, [field]: value }));

  const canSend = (questions || []).every((q) => (answers[q.field] || "").trim());

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!canSend || loading) return;
    const lines = (questions || []).map((q) => `${q.field}: ${(answers[q.field] || "").trim()}`);
    onAnswer(lines.join("\n"));
  };

  if (!questions || questions.length === 0) return null;

  return (
    <div className="trip-clarify">
      <h3>{message || "I need a few more details to plan your trip:"}</h3>
      <form onSubmit={handleSubmit}>
        {(questions || []).map((q) => (
          <div key={q.field} className="trip-q">
            <p className="trip-q-text">{q.question}</p>
            {q.why && <p className="trip-q-why">{q.why}</p>}
            {(q.options || []).length > 0 && (
              <div className="search-suggestions">
                {q.options.map((opt) => (
                  <button
                    key={opt}
                    type="button"
                    className={`sugg-chip${answers[q.field] === opt ? " active" : ""}`}
                    disabled={loading}
                    onClick={() => set(q.field, opt === "Other" ? "" : opt)}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            )}
            <input
              type="text"
              className="fl-input"
              placeholder={q.field === "budget" ? "e.g. 2500 or 'mid-range'" : "Type your answer…"}
              value={answers[q.field] || ""}
              disabled={loading}
              onChange={(e) => set(q.field, e.target.value)}
            />
          </div>
        ))}
        <button type="submit" className="search-btn" disabled={loading || !canSend}>
          {loading ? "Sending…" : (<>Send answers <Send size={15} /></>)}
        </button>
      </form>
    </div>
  );
}
