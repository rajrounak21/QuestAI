import { motion, useReducedMotion } from "framer-motion";
import Architecture3D from "./Architecture3D.jsx";
import ProductPreview from "./ProductPreview.jsx";

const ease = [0.22, 1, 0.36, 1];

export default function Hero() {
  const reduce = useReducedMotion();
  const anim = (delay) => reduce
    ? {}
    : { initial: { opacity: 0, y: 24 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.7, delay, ease } };

  return (
    <header
      className="hero" id="explore"
      onMouseMove={(e) => {
        const el = e.currentTarget;
        const r = el.getBoundingClientRect();
        el.style.setProperty("--sx", `${((e.clientX - r.left) / r.width) * 100}%`);
        el.style.setProperty("--sy", `${((e.clientY - r.top) / r.height) * 100}%`);
      }}
    >
      <div className="hero-spotlight" aria-hidden="true" />
      <div className="container">
        <motion.span className="eyebrow" {...anim(0)}>The AI Superapp</motion.span>
        <motion.h1 {...anim(0.08)}>
          One AI Superapp.<br />
          <span className="hl">Four specialized agents.</span>
        </motion.h1>
        <motion.p className="hero-copy" {...anim(0.16)}>
          Research anything, plan your next trip, compare products, or find your next
          opportunity — powered by specialized AI agents working behind one simple interface.
        </motion.p>
        <motion.div className="hero-ctas" {...anim(0.24)}>
          <a className="btn btn-primary btn-lg" href="/signup">
            Start Exploring <span className="arr" aria-hidden="true">→</span>
          </a>
          <a className="btn btn-secondary btn-lg" href="#how">See How It Works</a>
        </motion.div>
        <motion.p className="trust-line" {...anim(0.3)}>
          <b>Research</b> · <b>Travel</b> · <b>Shopping</b> · <b>Jobs</b> — one place, one experience
        </motion.p>

        <motion.div {...anim(0.36)}>
          <Architecture3D />
        </motion.div>
        <motion.div
          {...(reduce ? {} : {
            initial: { opacity: 0, y: 30, rotateX: 6 },
            whileInView: { opacity: 1, y: 0, rotateX: 0 },
            viewport: { once: true, margin: "-60px" },
            transition: { duration: 0.7, ease },
          })}
        >
          <ProductPreview />
        </motion.div>
      </div>
    </header>
  );
}
