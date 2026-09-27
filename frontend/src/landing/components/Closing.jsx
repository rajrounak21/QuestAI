import Reveal from "./Reveal.jsx";
import { BrandLockup } from "./BrandMark.jsx";
import { PhoneIcon } from "./icons.jsx";
import { STACK } from "../data.jsx";

export default function Closing() {
  return (
    <>
      <section className="section" id="stack" style={{ paddingTop: 20 }}>
        <div className="container" style={{ textAlign: "center" }}>
          <Reveal>
            <span className="eyebrow">System, not a wrapper</span>
            <h2 style={{ fontSize: "clamp(26px, 4vw, 40px)", margin: "14px 0 8px" }}>
              Built as a system of specialized AI agents.
            </h2>
            <p style={{ color: "var(--muted)", margin: 0, fontSize: 14.5 }}>
              Each agent owns its tools, schemas and evidence pipeline.
            </p>
            <div className="stack" aria-label="Technology stack">
              {STACK.map((s) => <span key={s}>{s}</span>)}
            </div>
          </Reveal>
        </div>
      </section>

      <section className="cta" id="cta">
        <div className="container">
          <Reveal>
            <div className="cta-card">
              <div className="cta-inner">
                <span className="eyebrow">Your next task starts here</span>
                <h2>Research it. Plan it.<br />Compare it. Find it.</h2>
                <p>One place. Multiple AI agents. One experience. Stop switching between tools.</p>
                <div className="hero-ctas">
                  <a className="btn btn-primary btn-lg" href="/signup">
                    Start Exploring <span className="arr" aria-hidden="true">→</span>
                  </a>
                  <a className="btn btn-secondary btn-lg" href="#agents">Explore the Agents</a>
                </div>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      <footer>
        <div className="container">
          <div className="foot-grid">
            <div className="foot-brand">
              <BrandLockup />
              <p className="foot-desc">
                One AI Superapp for research, travel, shopping and jobs — specialized agents behind one simple interface.
              </p>
            </div>
            <div>
              <h5>Product</h5>
              <a href="#agents">Research</a>
              <a href="#agents">Travel</a>
              <a href="#agents">Shopping</a>
              <a href="#agents">Jobs</a>
            </div>
            <div>
              <h5>Platform</h5>
              <a href="#how">How it works</a>
              <a href="#agents">Agents</a>
              <a href="#/about">About</a>
            </div>
            <div>
              <h5>Account</h5>
              <a href="/login">Log in</a>
              <a href="/signup">Get Started</a>
            </div>
          </div>
          <div className="foot-bottom">
            <span>© 2026 QuestAI</span>
            <span style={{ display: "flex", gap: 16 }}>
              <a className="foot-legal" href="#/privacy">Privacy</a>
              <a className="foot-legal" href="#/terms">Terms</a>
            </span>
          </div>
        </div>
      </footer>
    </>
  );
}
