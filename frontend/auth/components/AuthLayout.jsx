import NetworkCanvas from "./NetworkCanvas";
import { LogoMark } from "./ui";

const AGENTS = [
  { name: "Research", desc: "Deep reports with cited sources", accent: "#5b7cff" },
  { name: "Travel", desc: "Flights, hotels and trip plans", accent: "#56e1d5" },
  { name: "Shopping", desc: "Compare prices with evidence", accent: "#f472b6" },
  { name: "Jobs", desc: "Search, match and tailored CVs", accent: "#fbbf24" }
];

// Split-screen shell: branding left, card slot right.
// children = the auth card. notice = optional banner above card (reserved for verify-email later).
export default function AuthLayout({ children, notice }) {
  return (
    <div className="auth-page">
      <aside className="auth-brand">
        <NetworkCanvas />
        <div className="auth-glow" />
        <div className="auth-brand-inner">
          <div className="auth-logo">
            <LogoMark size={40} />
            <span className="auth-word">
              Quest<span className="auth-ai">AI</span>
            </span>
          </div>
          <div className="auth-badge">AI SUPERAPP</div>
          <h1 className="auth-headline">One account. Every intelligent workflow.</h1>
          <p className="auth-lede">
            Research, plan trips, compare products, and discover jobs with
            specialized AI agents from one place.
          </p>
          <div className="auth-agents">
            {AGENTS.map((a) => (
              <div className="auth-agent" key={a.name}
                style={{ "--agent": a.accent }}>
                <span className="auth-agent-name"><i />{a.name}</span>
                <span className="auth-agent-desc">{a.desc}</span>
              </div>
            ))}
          </div>
        </div>
      </aside>
      <main className="auth-main">
        <div style={{ width: "100%", maxWidth: 400 }}>
          {notice}
          {children}
        </div>
      </main>
    </div>
  );
}
