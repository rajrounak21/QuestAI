import { useState } from "react";
import { ChevronDown } from "lucide-react";

// Collapsible trip-embed section (flights / hotels grids).
// Default open so current behavior is preserved; user can collapse for scroll.
export default function Collapsible({ title, meta, badge, children, defaultOpen = true }) {
  const [open, setOpen] = useState(!!defaultOpen);
  return (
    <div className="trip-section trip-collapsible">
      <button
        type="button"
        className="trip-coll-head"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
      >
        <h3>{title} {meta && <span className="ext-text">{meta}</span>}</h3>
        {badge}
        <ChevronDown size={16} className={`trip-chevron${open ? " open" : ""}`} />
      </button>
      {open && children}
    </div>
  );
}
