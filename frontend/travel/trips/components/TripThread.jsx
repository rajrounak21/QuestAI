import { useEffect, useRef, useState } from "react";
import Clarifying from "./Clarifying";
import TripSearch from "./TripSearch";
import { timeAgo } from "../api";

const QUICK_ACTIONS = [
  { label: "Make it cheaper", kind: "budget", prompt: "Set my trip budget to $%v",
    hint: "New budget in USD", input: "number", min: 100 },
  { label: "Change dates", kind: "date", prompt: "Change trip departure date to %v",
    hint: "Pick a date", input: "date" },
  { label: "Add more days", kind: "days", prompt: "Add %v more days to the trip",
    hint: "How many days to add?", input: "number", min: 1, max: 30 },
  { label: "Nonstop flights only", kind: "direct", message: "Find nonstop flights" },
  { label: "What's the total?", kind: "direct", message: "What is my total cost?" },
];

// Unified left-right thread built from the persisted doc, so a reload
// rebuilds the same conversation. Assistant bubbles embed the trip detail.
export default function TripThread({
  doc,
  running,
  stale,
  elapsedText,
  onSend,
  onAnswerClarifying,
  onRetry,
  onSubmitDetails,
  renderTripDetail,
}) {
  const [text, setText] = useState("");
  const [echo, setEcho] = useState(null); // optimistic user bubble (cleared on server echo)
  const [activeAction, setActiveAction] = useState(null); // value-input quick action
  const [actionValue, setActionValue] = useState("");
  const [detailsOpen, setDetailsOpen] = useState(false); // confirm-details form modal
  const endRef = useRef(null);

  const status = doc?.status || null;
  const convo = doc?.conversation || [];
  const trip = doc?.trip || null;
  const allQs = doc?.clarifying_questions || [];
  const confirmQ = allQs.find((q) => q && q.field === "confirm_details");
  const otherQs = allQs.filter((q) => q && q.field !== "confirm_details");
  // Message count for scroll deps — computed null-safely before the guard.
  const msgCount = convo.length * 2 + (doc?.query ? 1 : 0);

  // Scroll only when the thread actually grows — never on keystrokes.
  // (Effects must stay above the early return: Rules of Hooks.)
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [msgCount, running, status]);

  // Drop the optimistic echo once the server turn arrives.
  useEffect(() => {
    if (echo && convo.some((t) => t.user === echo.text)) setEcho(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [convo.length]);

  // Guard — doc is null while the session loads; every line below
  // touches doc.query / convo and would crash the whole page otherwise.
  if (!doc) return null;

  const items = [];
  // Backend appends EVERY completion as a turn — including the first plan
  // run, whose user text duplicates doc.query. Skip that duplicate user
  // bubble (keep its assistant reply) so the input never appears twice.
  const firstDupesQuery = convo.length > 0 && doc.query && convo[0].user === doc.query;
  if (doc.query && !firstDupesQuery) items.push({ key: "q0", role: "user", text: doc.query });
  convo.forEach((t, i) => {
    if (!(i === 0 && firstDupesQuery)) {
      items.push({ key: `u${i}`, role: "user", text: t.user, at: t.at });
    }
    items.push({
      key: `a${i}`, role: "assistant", text: t.assistant, at: t.at,
      isLast: i === convo.length - 1,
    });
  });

  const showTripEmbeds = (m) =>
    m.isLast && status === "ready" && trip?.destination && renderTripDetail;

  const fire = (msg) => {
    const m = (msg || "").trim();
    if (!m || running) return;
    setEcho({ text: m, key: `echo-${Date.now()}` });
    setActiveAction(null);
    setActionValue("");
    onSend(m);
  };

  const submit = (e) => {
    e.preventDefault();
    const msg = text.trim();
    if (!msg || running) return;
    setText("");
    fire(msg);
  };

  const submitActionValue = (e) => {
    e.preventDefault();
    if (!activeAction || running) return;
    const v = (actionValue || "").trim();
    if (!v) return;
    if (activeAction.input === "number" && !(Number(v) > 0)) return;
    fire(activeAction.prompt.replace("%v", v));
  };

  return (
    <div className="trip-thread">
      <div className="chat-messages">
        {items.map((m) =>
          m.role === "user" ? (
            <div key={m.key} className="chat-message user">
              <div className="user-bubble">
                {m.text}
                {m.at && <span className="bubble-time">{timeAgo(m.at)}</span>}
              </div>
            </div>
          ) : (
            <div key={m.key} className="chat-message assistant">
              <div className="message-avatar">✈</div>
              <div className="assistant-bubble">
                <p>{m.text}</p>
                {m.at && <span className="bubble-time">{timeAgo(m.at)}</span>}
                {showTripEmbeds(m) && (
                  <div className="trip-result-inline">{renderTripDetail()}</div>
                )}
                {m.isLast && status === "awaiting_input" && (
                  <>
                    {otherQs.length > 0 && (
                      <Clarifying
                        questions={otherQs}
                        message=""
                        loading={running}
                        onAnswer={onAnswerClarifying}
                      />
                    )}
                    {confirmQ && (
                      <div className="confirm-details-cta">
                        <p>{confirmQ.question || "Review the trip details:"}</p>
                        <button
                          type="button"
                          className="search-btn"
                          disabled={running}
                          onClick={() => setDetailsOpen(true)}
                        >
                          Review trip details
                        </button>
                      </div>
                    )}
                  </>
                )}
                {m.isLast && status === "failed" && (
                  <button className="btn-again" onClick={onRetry}>
                    Try again
                  </button>
                )}
              </div>
            </div>
          )
        )}
        {echo && (
          <div key={echo.key} className="chat-message user">
            <div className="user-bubble">
              {echo.text}
              <span className="bubble-time">sending…</span>
            </div>
          </div>
        )}
        {running && (
          <div className="chat-message assistant">
            <div className="message-avatar">✈</div>
            <div className="assistant-bubble typing">
              <span className="typing-dots"><span /><span /><span /></span>
              {elapsedText && <span className="ext-text"> · {elapsedText}</span>}
              {stale && <span className="ext-text"> · still working…</span>}
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {status === "ready" && !running && (
        <div className="quick-actions">
          {QUICK_ACTIONS.map((a) => (
            <button
              key={a.label}
              type="button"
              className={`quick-action${activeAction?.label === a.label ? " active" : ""}`}
              disabled={running}
              onClick={() => {
                if (a.kind === "direct") fire(a.message);
                else {
                  setActiveAction(activeAction?.label === a.label ? null : a);
                  setActionValue("");
                }
              }}
            >
              {a.label}
            </button>
          ))}
        </div>
      )}

      {activeAction && status === "ready" && !running && (
        <form className="qa-input-row" onSubmit={submitActionValue}>
          <span className="qa-label">{activeAction.label}: {activeAction.hint}</span>
          <input
            className="chat-input"
            type={activeAction.input === "date" ? "date" : "number"}
            value={actionValue}
            min={activeAction.min}
            max={activeAction.max}
            onChange={(e) => setActionValue(e.target.value)}
            placeholder={activeAction.input === "date" ? "Pick a date" : "Enter amount"}
            autoComplete="off"
            autoFocus
          />
          <button type="submit" className="chat-send-btn" disabled={!actionValue.trim()} aria-label="Send value">
            →
          </button>
          <button type="button" className="btn-ghost" onClick={() => { setActiveAction(null); setActionValue(""); }}>
            Cancel
          </button>
        </form>
      )}

      <form className="chat-input-bar" onSubmit={submit}>
        <input
          className="chat-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={
            status === "ready"
              ? "e.g., Make it cheaper, change dates…"
              : "Ask anything…"
          }
          disabled={running}
          autoComplete="off"
        />
        <button type="submit" className="chat-send-btn" disabled={running || !text.trim()} aria-label="Send">
          →
        </button>
      </form>

      {detailsOpen && confirmQ && (
        <div className="sh-modal-wrap" onClick={() => setDetailsOpen(false)}>
          <div
            className="sh-modal trip-details-modal"
            onClick={(e) => e.stopPropagation()}
          >
            <h4>{confirmQ.question || "Review trip details"}</h4>
            <p className="sh-modal-q">
              Prefilled below — edit anything, then pick where it goes.
            </p>
            <TripSearch
              initialValues={doc.pending_preview || {}}
              loading={running}
              actions={[
                { id: "create", label: "Create new session" },
                { id: "overwrite", label: "Overwrite this trip", primary: false },
              ]}
              onSearch={(query, actionId) => {
                setDetailsOpen(false);
                if (onSubmitDetails) onSubmitDetails(query, actionId || "create");
              }}
            />
            <div className="sh-modal-actions" style={{ marginTop: 4 }}>
              <button className="btn-ghost" onClick={() => setDetailsOpen(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
