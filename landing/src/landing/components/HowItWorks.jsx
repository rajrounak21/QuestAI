import Reveal from "./Reveal.jsx";
import { STEPS } from "../data.jsx";

export default function HowItWorks() {
  return (
    <section className="section" id="how">
      <div className="container">
        <Reveal className="head center">
          <span className="eyebrow">How it works</span>
          <h2>From request to result.</h2>
          <p>Type what you need. The platform routes it. A specialist delivers it.</p>
        </Reveal>
        <div className="steps" role="list">
          {STEPS.map((s, i) => (
            <Reveal key={s.n} delay={i * 0.1}>
              <article className="panel step" role="listitem">
                <div className="n">{String(i + 1).padStart(2, "0")} · {s.n}</div>
                <h3>{s.title}</h3>
                <p>{s.desc}</p>
                <div className="step-connector" aria-hidden="true">
                  <span className="step-line" />
                  <span style={{ color: "var(--accent)", fontWeight: 800 }}>→</span>
                </div>
              </article>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
