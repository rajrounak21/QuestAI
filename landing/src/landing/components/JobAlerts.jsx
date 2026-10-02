import Reveal from "./Reveal.jsx";
import { BellIcon } from "./icons.jsx";

const PIPE = [
  { t: "Job Search", s: "criteria → query" },
  { t: "Fresh Job Detection", s: "new matches only" },
  { t: "Personalized Alert", s: "ranked for you" },
  { t: "Branded Email", s: "in your inbox" },
];

export default function JobAlerts() {
  return (
    <section className="section" id="alerts" style={{ paddingTop: 20 }}>
      <div className="container">
        <Reveal>
          <div className="panel alerts">
            <div>
              <span className="eyebrow">Jobs automation</span>
              <h2 style={{ fontSize: "clamp(28px, 4vw, 44px)", lineHeight: 1.08, margin: "14px 0" }}>
                Don’t just find jobs.<br />Stay ahead of them.
              </h2>
              <p style={{ color: "var(--muted)", fontSize: 14.5 }}>
                Automated job alerts keep you informed when new matching opportunities appear —
                no daily searching, no missed postings.
              </p>
              <div className="pipeline" aria-label="Job alert pipeline">
                {PIPE.map((p, i) => (
                  <div key={p.t}>
                    <div className="pipe-step">
                      <span style={{
                        width: 26, height: 26, borderRadius: 8, display: "grid",
                        placeItems: "center", background: "var(--accent-soft)",
                        color: "#b9c4ff", fontSize: 12, fontWeight: 800,
                      }}>{i + 1}</span>
                      {p.t}<small>{p.s}</small>
                    </div>
                    {i < PIPE.length - 1 && <div className="pipe-arrow" aria-hidden="true" />}
                  </div>
                ))}
              </div>
            </div>
            <div className="email-card" role="img" aria-label="Preview of a branded job alert email with three new AI Engineer Intern roles">
              <div className="email-head">
                <span className="bell" aria-hidden="true"><BellIcon size={19} /></span>
                <div>
                  <div style={{ fontWeight: 800, fontSize: 14 }}>3 new jobs for AI Engineer Intern</div>
                  <div style={{ color: "var(--muted)", fontSize: 12 }}>QuestAI Jobs · just now · personalized</div>
                </div>
              </div>
              <div className="email-body">
                {[
                  ["AI Engineer Intern", "Sarvam AI · Remote · India · 94%"],
                  ["ML Intern", "Krutrim · Bengaluru · 91%"],
                  ["GenAI Intern", "Yellow.ai · Remote · 87%"],
                ].map(([t, m]) => (
                  <div className="email-job" key={t}>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: 13.5 }}>{t}</div>
                      <div style={{ color: "var(--muted)", fontSize: 12 }}>{m}</div>
                    </div>
                    <div style={{ display: "flex", gap: 6 }}>
                      <button className="mini-btn" type="button">View Job</button>
                      <button className="mini-btn primary" type="button">Apply</button>
                    </div>
                  </div>
                ))}
                <div style={{ color: "var(--muted2)", fontSize: 11, fontFamily: "var(--mono)", textAlign: "center" }}>
                  You care about the result — not the automation behind it.
                </div>
              </div>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
