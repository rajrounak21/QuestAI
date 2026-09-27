import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { authFetch, clearAuth, getToken } from "./api";
import { BellIcon, BriefcaseIcon, MenuIcon, SendIcon, SparkleIcon } from "./components/icons";
import { LogoMark, ThemeToggle } from "./components/ui";

const NAV = ["Home", "Research", "Travel", "Shopping", "Jobs"];
const AGENTS = ["Auto", "Research", "Travel", "Shopping", "Jobs"];

const SUGGESTIONS = [
  { agent: "Research", text: "Compare RAG evaluation frameworks" },
  { agent: "Travel", text: "Find flights from Delhi to Dubai" },
  { agent: "Shopping", text: "Compare phones under ₹30,000" },
  { agent: "Jobs", text: "Find AI internships in India" },
];

const ACTIVITY = [
  { agent: "Research", title: "RAG evaluation frameworks", when: "2 hours ago" },
  { agent: "Travel", title: "Delhi → Dubai flights", when: "Yesterday" },
  { agent: "Jobs", title: "AI Engineer internships", when: "Yesterday" },
];

const AGENT_ROWS = [
  { name: "Research", desc: "Deep research, evidence and structured answers" },
  { name: "Travel", desc: "Flights, hotels and trip plans" },
  { name: "Shopping", desc: "Compare products and prices" },
  { name: "Jobs", desc: "Find and monitor opportunities" },
];

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

function maskEmail(email = "") {
  const [u, d] = email.split("@");
  if (!u || !d) return email;
  return `${u[0]}***@${d}`;
}

export default function Home() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [netDown, setNetDown] = useState(false);
  const [active, setActive] = useState("Home");
  const [menu, setMenu] = useState(false);
  const [profile, setProfile] = useState(false);
  const [agent, setAgent] = useState("Auto");
  const [query, setQuery] = useState("");
  const [routing, setRouting] = useState(null); // { steps:[], done, label }

  useEffect(() => {
    if (!getToken()) {
      navigate("/login", { replace: true });
      return;
    }
    loadUser();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadUser = () => {
    setLoading(true);
    setNetDown(false);
    authFetch("/api/auth/me")
      .then(async (res) => {
        if (!res || res.unauthorized) {
          // Real auth failure only: tokens dead -> fresh login required.
          clearAuth();
          navigate("/login", { replace: true });
          return;
        }
        if (res.networkError) {
          // Backend unreachable: tokens untouched, stay on /home, offer retry.
          setLoading(false);
          setNetDown(true);
          return;
        }
        const data = await res.json();
        setUser(data.user);
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
        setNetDown(true);
      });
  };

  const firstName = useMemo(() => {
    if (!user) return "";
    if (user.name) return user.name.split(" ")[0];
    return user.email.split("@")[0];
  }, [user]);

  const logout = () => {
    clearAuth();
    navigate("/login", { replace: true });
  };

  const submit = (e) => {
    e.preventDefault();
    const q = query.trim();
    if (!q || routing) return;
    const label = agent === "Auto" ? "Auto" : agent;
    const steps =
      agent === "Auto"
        ? ["Understanding request", "Choosing best agent", "Universal router connects here soon"]
        : [`Understanding request`, `Routing to ${label}`, `${label} workspace connects here soon`];
    setRouting({ q, steps, shown: 0, done: false });
  };

  useEffect(() => {
    if (!routing || routing.done) return;
    if (routing.shown >= routing.steps.length) {
      const t = setTimeout(() => setRouting((r) => ({ ...r, done: true })), 600);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setRouting((r) => ({ ...r, shown: r.shown + 1 })), 900);
    return () => clearTimeout(t);
  }, [routing]);

  if (loading) {
    return (
      <div className="dash">
        <p className="dash-loading">Loading your workspace...</p>
      </div>
    );
  }

  if (netDown) {
    return (
      <div className="dash">
        <div className="dash-offline">
          <h1>Can&apos;t reach the server.</h1>
          <p className="auth-sub">Your session is safe. Start the backend and retry.</p>
          <button className="btn-primary" style={{ maxWidth: 220 }} onClick={loadUser}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="dash">
      <header className="dash-top">
        <div className="dash-left">
          <Link to="/" className="dash-brand" title="Back to landing page">
            <LogoMark size={30} />
            <span className="auth-word" style={{ fontSize: 17 }}>
              Quest<span className="auth-ai">AI</span>
            </span>
          </Link>
          <nav className={`dash-nav${menu ? " open" : ""}`}>
            {NAV.map((n) => (
              <button key={n} className={`dash-navlink${active === n ? " active" : ""}`}
                onClick={() => { setActive(n); setMenu(false); }}>
                {n}
              </button>
            ))}
          </nav>
        </div>
        <div className="dash-right">
          <ThemeToggle />
          <button className="dash-iconbtn" title="Notifications" onClick={() => setMenu(false)}><BellIcon /></button>
          <div className="dash-profile">
            <button className="dash-userbtn" onClick={() => setProfile((p) => !p)}>
              {firstName} ▾
            </button>
            {profile && (
              <div className="dash-menu">
                <div className="dash-menu-head">
                  <strong>{user.name || firstName}</strong>
                  <span>{maskEmail(user.email)}</span>
                </div>
                {["Profile", "Settings", "Alerts"].map((x) => (
                  <button key={x} className="dash-menuitem" onClick={() => setProfile(false)}>{x}</button>
                ))}
                <div className="dash-menudiv" />
                <button className="dash-menuitem" onClick={logout}>Sign out</button>
              </div>
            )}
          </div>
          <button className="dash-burger" onClick={() => setMenu((m) => !m)}><MenuIcon /></button>
        </div>
      </header>

      <main className="dash-main dash-wide">
        <section className="dash-hero">
          <h1>{greeting()}, {firstName}</h1>
          <p className="auth-sub">What can I help you with today?</p>
          <form onSubmit={submit} className="dash-ask">
            <input
              placeholder="Ask anything..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <button type="submit" aria-label="Send"><SendIcon /></button>
          </form>
          <p className="dash-hint">Ask anything. I&apos;ll figure out which AI agent can help.</p>
          <div className="dash-pills">
            <span className="dash-pills-label">What do you want to do?</span>
            <div className="dash-pills-row">
              {AGENTS.map((a) => (
                <button key={a} className={`dash-pill${agent === a ? " active" : ""}`}
                  onClick={() => setAgent(a)}>
                  {a === "Auto" ? (<><SparkleIcon /> Auto</>) : a}
                </button>
              ))}
            </div>
          </div>
          <div className="dash-suggest">
            <p className="dash-sect-label">Try asking</p>
            <div className="dash-suggest-grid">
              {SUGGESTIONS.map((s) => (
                <button key={s.text} className="dash-suggest-card"
                  onClick={() => { setQuery(s.text); setAgent(s.agent); }}>
                  <strong>{s.agent}</strong>
                  <span>&ldquo;{s.text}&rdquo;</span>
                </button>
              ))}
            </div>
          </div>
        </section>

        {routing && (
          <section className="dash-route">
            <p className="dash-sect-label">Your request</p>
            <p className="dash-route-q">&ldquo;{routing.q}&rdquo;</p>
            <div className="dash-steps">
              {routing.steps.slice(0, routing.shown).map((s, i) => (
                <p key={i} className={i === 1 ? "dash-core" : ""}>
                  {i === 1 ? (<><SparkleIcon size={13} /> </>) : "↓ "}{s}
                </p>
              ))}
            </div>
            {routing.done && (
              <button className="auth-link" onClick={() => setRouting(null)}>Dismiss</button>
            )}
          </section>
        )}

        <section>
          <p className="dash-sect-label">Recent activity</p>
          <div className="dash-activity">
            {ACTIVITY.map((a) => (
              <div className="dash-act-card" key={a.title}>
                <strong>{a.agent}</strong>
                <span className="dash-act-title">{a.title}</span>
                <div className="dash-act-foot">
                  <span>{a.when}</span>
                  <button className="auth-link">Open →</button>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section>
          <p className="dash-sect-label">Your agents</p>
          <p className="dash-sect-sub">Specialized intelligence, whenever you need it.</p>
          <div className="dash-agentrows">
            {AGENT_ROWS.map((a) => (
              <div className="dash-agentrow" key={a.name}>
                <div>
                  <strong>{a.name}</strong>
                  <span>{a.desc}</span>
                </div>
                <button className="auth-link">Explore →</button>
              </div>
            ))}
          </div>
        </section>

        <section>
          <p className="dash-sect-label">Job alerts</p>
          <div className="dash-alert">
            <div>
              <strong><BriefcaseIcon size={15} /> AI Engineer Intern</strong>
              <span>India · Daily · 10:45 AM</span>
            </div>
            <div className="dash-alert-row">
              <span>Last check · 4 new jobs</span>
              <button className="auth-link">View Alert</button>
            </div>
          </div>
          <button className="btn-google" style={{ maxWidth: 220, height: 44 }}>
            + Create job alert
          </button>
        </section>
      </main>
    </div>
  );
}
