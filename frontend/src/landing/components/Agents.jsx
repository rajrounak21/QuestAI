import Reveal from "./Reveal.jsx";
import { AGENTS } from "../data.jsx";

// Every agent opens a dedicated full-page graph flow.
const FLOW_LINKS = {
  research: "#/flow/research",
  shopping: "#/flow/shopping",
  travel: "#/flow/travel",
  jobs: "#/flow/jobs",
};

export default function Agents() {
  return (
    <section className="section" id="agents">
      <div className="container">
        <Reveal className="head center">
          <span className="eyebrow">Agent showcase</span>
          <h2>Four agents. One experience.</h2>
          <p>Each agent is specialized for a different kind of task, while the platform keeps the experience consistent.</p>
        </Reveal>
        <div className="agents-grid">
          {AGENTS.map((a, i) => (
            <Reveal key={a.id} delay={i * 0.08}>
              <article
                className="panel agent-card"
                style={{ "--ac": a.accent, "--ac-soft": a.soft, "--ac-line": a.line }}
                onMouseMove={(e) => {
                  const el = e.currentTarget;
                  const r = el.getBoundingClientRect();
                  el.style.setProperty("--mx", `${((e.clientX - r.left) / r.width) * 100}%`);
                  el.style.setProperty("--my", `${((e.clientY - r.top) / r.height) * 100}%`);
                }}
              >
                <div className="agent-ic" style={{ background: a.soft, color: a.accent, borderColor: a.line }}>
                  {a.icon}
                </div>
                <small className="agent-tag">Agent {a.index}</small>
                <h3>{a.title}</h3>
                <p>{a.desc}</p>
                <ul className="caps">
                  {a.caps.map((c) => <li key={c}>{c}</li>)}
                </ul>
                <div style={{ marginTop: 16 }}>
                  <a
                    className="link-arrow"
                    href={FLOW_LINKS[a.id] || "#cta"}
                    aria-label={`${a.cta} — ${a.title}`}
                  >
                    {a.cta} <span aria-hidden="true">→</span>
                  </a>
                </div>
              </article>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
