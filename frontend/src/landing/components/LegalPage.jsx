import Reveal from "./Reveal.jsx";
import { BrandMark } from "./BrandMark.jsx";
import { ArrowLeftIcon, PhoneIcon } from "./icons.jsx";
import { LEGAL } from "../legalCopy.js";

export default function LegalPage({ doc }) {
  const copy = LEGAL[doc] ?? LEGAL.privacy;
  const other = doc === "privacy" ? "terms" : "privacy";

  return (
    <>
      <div className="bg-grid" aria-hidden="true" />
      <div className="bg-glow" aria-hidden="true" />
      <nav className="nav scrolled" aria-label="Primary">
        <div className="container nav-inner">
          <BrandMark />
          <div className="nav-cta">
            <a className="btn btn-secondary" href="#top" style={{ minHeight: 38, fontSize: 13 }}>
              <ArrowLeftIcon /> Back to home
            </a>
          </div>
        </div>
      </nav>
      <main className="container legal-page">
        <Reveal>
          <span className="eyebrow">QuestAI · Legal</span>
          <h1>{copy.title}</h1>
          <p className="legal-updated">{copy.updated}</p>
          <p className="legal-intro">{copy.intro}</p>
        </Reveal>
        <Reveal delay={0.1}>
          <div className="panel legal-card">
            {copy.sections.map(([h, p], i) => (
              <section key={h}>
                <h2><span className="legal-num">{String(i + 1).padStart(2, "0")}</span> {h}</h2>
                <p>{p}</p>
              </section>
            ))}
          </div>
        </Reveal>
        <Reveal delay={0.15}>
          <div className="panel legal-contact">
            <div>
              <h2>Questions?</h2>
              <p>Reach out — we respond within a reasonable time.</p>
            </div>
            <a className="btn btn-primary" href="mailto:rajrounak366@gmail.com">
              rajrounak366@gmail.com
            </a>
          </div>
          <p className="legal-switch">
            Looking for the {other === "privacy" ? "Privacy Policy" : "Terms of Service"} instead?{" "}
            <a href={`#/${other}`}>Read it here →</a>
          </p>
        </Reveal>
      </main>
      <footer>
        <div className="container foot-bottom" style={{ borderTop: 0, marginTop: 0 }}>
          <span>© 2026 QuestAI</span>
          <span style={{ display: "flex", gap: 16 }}>
            <a className="foot-legal" href="#/privacy">Privacy</a>
            <a className="foot-legal" href="#/terms">Terms</a>
          </span>
        </div>
      </footer>
    </>
  );
}
