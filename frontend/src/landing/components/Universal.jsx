import { useState } from "react";
import Reveal from "./Reveal.jsx";

const ROUTES = {
  "Compare Samsung phones under ₹30,000": "shopping",
  "Find AI Engineer internships in India": "jobs",
  "Research open-source RAG tools": "research",
  "Delhi → Dubai under  $50": "travel",
};

export default function Universal() {
  const [demo, setDemo] = useState("Find AI Engineer internships in India");
  const on = ROUTES[demo];

  return (
    <section className="section" id="universal">
      <div className="container">
        <Reveal>
          <div className="panel universal">
            <div>
              <span className="eyebrow">Universal intelligence</span>
              <h2 style={{ fontSize: "clamp(28px, 4vw, 44px)", lineHeight: 1.06, margin: "14px 0" }}>
                One interface.<br />Specialized intelligence underneath.
              </h2>
              <p style={{ color: "var(--muted)", fontSize: 14.5 }}>
                You don’t need to understand which agent to use. Describe the task.
                The platform handles the routing — each request flows through a
                universal layer to exactly one specialist.
              </p>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 16 }}>
                {Object.keys(ROUTES).map((q) => (
                  <button
                    key={q} type="button" onClick={() => setDemo(q)}
                    className="mini-btn" aria-pressed={demo === q}
                    style={demo === q
                      ? { borderColor: "rgba(91,124,255,0.55)", background: "var(--accent-soft)", color: "#fff" }
                      : undefined}
                  >
                    {q.length > 34 ? q.slice(0, 34) + "…" : q}
                  </button>
                ))}
              </div>
              <p style={{ fontFamily: "var(--mono)", fontSize: 11.5, color: "var(--muted2)", marginTop: 12 }}>
                “{demo}” → <b style={{ color: "#b9c4ff" }}>{on}</b> ✓ · described architecture, no magic claims
              </p>
            </div>
            <div className="uni-flow" aria-label="Universal routing architecture diagram">
              <div className="uni-node user">User</div>
              <div className="uni-link" aria-hidden="true" />
              <div className="uni-node user">Natural language</div>
              <div className="uni-link" aria-hidden="true" />
              <div className="uni-node core">Universal Layer</div>
              <div className="uni-link" aria-hidden="true" />
              <div className="uni-agents">
                {["research", "travel", "shopping", "jobs"].map((a) => (
                  <div key={a} className={`uni-agent${on === a ? " on" : ""}`}>
                    {a[0].toUpperCase() + a.slice(1)}{on === a ? " ✓" : ""}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
