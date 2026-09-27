import Reveal from "./Reveal.jsx";
import { EXAMPLES } from "../data.jsx";

export default function Examples() {
  return (
    <section className="section" id="examples" style={{ paddingTop: 20 }}>
      <div className="container">
        <Reveal className="head center">
          <span className="eyebrow">Real tasks</span>
          <h2>Ask it anything within its world.</h2>
          <p>Four examples that make the product immediately understandable.</p>
        </Reveal>
        <div className="examples-grid">
          {EXAMPLES.map((e, i) => (
            <Reveal key={e.q} delay={i * 0.07}>
              <button type="button" className="example"
                onClick={() => document.getElementById("explore")?.scrollIntoView({ behavior: "smooth" })}
                aria-label={`Try example: ${e.q}`}>
                <q>{e.q}</q>
                <span className="ex-badge" style={{ color: e.color, borderColor: `${e.color}55`, background: `${e.color}14` }}>
                  {e.badge}
                </span>
              </button>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
