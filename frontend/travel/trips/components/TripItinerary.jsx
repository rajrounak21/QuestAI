import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { currencySymbol } from "../api";

// Day-by-day itinerary timeline. Each day opens/closes; first day starts
// open. Expand-all / collapse-all toggle in the section head.
export default function TripItinerary({ days, currency }) {
  const list = days || [];
  const [open, setOpen] = useState(() => new Set([0]));

  if (list.length === 0) return null;

  const toggle = (i) => {
    setOpen((cur) => {
      const next = new Set(cur);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  };

  const allOpen = open.size === list.length;
  const toggleAll = () => {
    setOpen(allOpen ? new Set() : new Set(list.map((_, i) => i)));
  };

  return (
    <div className="trip-section">
      <div className="trip-section-head">
        <h3>Day-by-day itinerary</h3>
        <button type="button" className="btn-ghost btn-sm" onClick={toggleAll}>
          {allOpen ? "Collapse all" : "Expand all"}
        </button>
      </div>
      <div className="trip-timeline">
        {list.map((d, i) => {
          const isOpen = open.has(i);
          const acts = d.activities || [];
          const dayTotal = acts.reduce((s, a) => s + (Number(a.estimated_cost) || 0), 0);
          return (
            <div key={d.day || i} className={`trip-day${isOpen ? " open" : ""}`}>
              <button
                type="button"
                className="trip-day-head"
                onClick={() => toggle(i)}
                aria-expanded={isOpen}
              >
                <span className="trip-day-num">Day {d.day || i + 1}</span>
                {d.date && <span className="ext-text">{d.date}</span>}
                {d.title && <strong>{d.title}</strong>}
                <span className="ext-text trip-day-meta">
                  {acts.length} stops
                  {dayTotal > 0 && (
                    <> · ≈ {currencySymbol(currency)}{Math.round(dayTotal).toLocaleString()}</>
                  )}
                </span>
                <ChevronDown size={16} className={`trip-chevron${isOpen ? " open" : ""}`} />
              </button>
              {isOpen && (
                <div className="trip-acts">
                  {acts.map((a, j) => (
                    <div key={j} className="trip-act">
                      <div className="trip-act-main">
                        {a.time && <span className="trip-act-time">{a.time}</span>}
                        <strong>{a.name}</strong>
                        {a.location && <span className="ext-text"> · {a.location}</span>}
                      </div>
                      {a.description && <p className="ext-text">{a.description}</p>}
                      <div className="trip-act-foot">
                        {a.estimated_cost > 0 && (
                          <span className="ext-text">
                            ≈ {currencySymbol(currency)}{Math.round(a.estimated_cost).toLocaleString()}
                          </span>
                        )}
                        {a.source_url && (
                          <a href={a.source_url} target="_blank" rel="noopener noreferrer" className="auth-link">
                            Source →
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
