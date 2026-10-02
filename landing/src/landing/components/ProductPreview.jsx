import { useReducedMotion } from "framer-motion";
import { useTilt } from "../hooks.js";
import { SparkIcon } from "./icons.jsx";

export default function ProductPreview() {
  const reduce = useReducedMotion();
  const { ref, onMove, onLeave, style } = useTilt(6);

  return (
    <div className="preview-wrap">
      <div ref={ref} className="preview" style={reduce ? undefined : style}
        onMouseMove={onMove} onMouseLeave={onLeave}>
        <div className="preview-glare" aria-hidden="true" />
        <div className="preview-bar" aria-hidden="true">
          <i /><i /><i />
          <span style={{ marginLeft: 8, fontSize: 12, color: "var(--muted)" }}>questai.app/preview</span>
          <span className="agent-badge" style={{ marginLeft: "auto" }}>Jobs · live preview</span>
        </div>
        <div className="preview-body">
          <div className="query-row">
            <span className="q-icon" aria-hidden="true"><SparkIcon size={15} /></span>
            <span>Find AI Engineer internships in India</span>
          </div>
          <div className="agent-row">
            <span className="agent-badge">AI Agent · Jobs</span>
            <span>3 matches · resume-aware · updated 2h ago</span>
          </div>
          <div className="job-card">
            <div>
              <h4>AI Engineer Intern</h4>
              <div className="comp">Sarvam AI · Bengaluru</div>
              <div className="job-meta">Remote · India · Posted 2 days ago · 94% match</div>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="mini-btn" type="button">View Job</button>
              <button className="mini-btn primary" type="button">Apply</button>
            </div>
          </div>
          <div className="job-card" style={{ marginTop: 10, opacity: 0.85 }}>
            <div>
              <h4>Generative AI Intern</h4>
              <div className="comp">Yellow.ai · Remote India</div>
              <div className="job-meta">Remote · Posted 4 days ago · 87% match</div>
            </div>
            <button className="mini-btn" type="button">View Job</button>
          </div>
        </div>
      </div>
    </div>
  );
}
