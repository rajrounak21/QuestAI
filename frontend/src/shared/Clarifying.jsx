import { useState } from "react";
import { Send } from "lucide-react";
import "./clarifying.css";

/**
 * Asks for the fields a specialist needs before it can run.
 *
 * One component, two callers: the trip graph mid-plan (its validator emits
 * {field, question, why, options}) and the Home page before handing over to an
 * agent whose router receipt reported missing required fields. Same shape, same
 * interaction, so a question reads identically either way.
 *
 * Option chips with free text underneath. "Other" clears the field so the user
 * can type instead.
 */
export default function Clarifying({ questions, message, loading, onAnswer, submitLabel = "Send answers" }) {
  const [answers, setAnswers] = useState({});

  const set = (field, value) => setAnswers((cur) => ({ ...cur, [field]: value }));

  const list = questions || [];
  const canSend = list.length > 0 && list.every((q) => (answers[q.field] || "").trim());

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!canSend || loading) return;
    onAnswer(list.map((q) => `${q.field}: ${answers[q.field].trim()}`).join("\n"));
  };

  if (list.length === 0) return null;

  return (
    <div className="trip-clarify">
      {message && <h3>{message}</h3>}
      <form onSubmit={handleSubmit}>
        {list.map((q) => (
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
              type={q.inputType || "text"}
              className="fl-input"
              placeholder={
                q.placeholder ||
                (q.inputType === "date" ? "" : "Type your answer\u2026")
              }
              value={answers[q.field] || ""}
              disabled={loading}
              onChange={(e) => set(q.field, e.target.value)}
            />
          </div>
        ))}
        <button type="submit" className="search-btn" disabled={loading || !canSend}>
          {loading ? "Sending\u2026" : (<>{submitLabel} <Send size={15} /></>)}
        </button>
      </form>
    </div>
  );
}