import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { authFetch, clearAuth, getToken, routeIntent, askAssistant } from "./api";
import { BellIcon, BriefcaseIcon, MenuIcon, SendIcon } from "./components/icons";
import AgentSelect from "./components/AgentSelect";
import { AGENT_BY_ID, AGENT_OPTIONS, DEFAULT_AGENT_ID } from "../src/shared/agents";
import { LogoMark, ThemeToggle } from "./components/ui";
import OtpModal from "./components/OtpModal";
import VerifyBanner from "./components/VerifyBanner";
import Clarifying from "../src/shared/Clarifying";
import { asksFor } from "../src/shared/agentFields";
import { mergeFields } from "../src/shared/mergeFields";

const VERIFY_SKIP_KEY = "questai_verify_skipped";
const readVerifySkipped = () => {
  try {
    return localStorage.getItem(VERIFY_SKIP_KEY) === "1";
  } catch {
    return false;
  }
};
const writeVerifySkipped = () => {
  try {
    localStorage.setItem(VERIFY_SKIP_KEY, "1");
  } catch {
    /* private mode / storage disabled — banner simply reappears next visit */
  }
};
const clearVerifySkipped = () => {
  try {
    localStorage.removeItem(VERIFY_SKIP_KEY);
  } catch {
    /* ignore */
  }
};

const AGENT_LABELS = {
  research: "Research",
  shopping: "Shopping",
  jobs: "Jobs",
  flights: "Flights",
  hotels: "Hotels",
  trips: "Trips",
};

/**
 * Naming the step turns a 2-3s pause into something legible. Three anonymous
 * dots read as a hang; "Finding the right agent" reads as work happening.
 */
function thinkingLabel(q = "") {
  const t = String(q).toLowerCase();
  if (/\b(flight|fly|flying|airline|ticket)\b/.test(t)) return "Looking for flights\u2026";
  if (/\b(hotel|hostel|resort|stay|staying)\b/.test(t)) return "Looking for stays\u2026";
  if (/\b(job|career|hiring|internship|vacancy|recruit)\b/.test(t)) return "Looking for roles\u2026";
  if (/\b(buy|shop|purchase|price|cheapest|product|budget)\b/.test(t)) return "Looking for products\u2026";
  if (/\b(trip|itinerary|holiday|vacation|plan)\b/.test(t)) return "Planning the route\u2026";
  return "Finding the right agent\u2026";
}

const NAV = ["Home", "Research", "Travel", "Shopping", "Jobs"];
const NAV_PATH = {
  Research: "/research",
  Shopping: "/shopping",
  // The header keeps one "Travel" entry pointing at the trip planner; the
  // dropdown is where Flights and Hotels are picked individually.
  Travel: "/trips",
  Jobs: "/jobs",
};
// Agent list lives in src/shared/agents.js so the dropdown, submit() routing
// and the suggestion cards all read from one place.

// Recent-activity cards open their saved session. A lookup beats a nested
// ternary here: Jobs was silently missing from the old chain, so job cards
// opened /research/<id> instead of /jobs/<id>.
const ACTIVITY_PATH = {
  Research: "/research",
  Shopping: "/shopping",
  Flights: "/flights",
  Hotels: "/hotels",
  Trips: "/trips",
  Jobs: "/jobs",
};

const SUGGESTIONS = [
  { agent: "research", text: "Compare RAG evaluation frameworks" },
  { agent: "flights", text: "Find flights from Delhi to Dubai" },
  { agent: "hotels", text: "Find hotels in Bali for 5 nights" },
  { agent: "shopping", text: "Compare phones under ₹30,000" },
  { agent: "jobs", text: "Find AI internships in India" },
];

function timeAgo(iso) {
  if (!iso) return "";
  let str = String(iso);
  if (!str.endsWith("Z") && !str.includes("+") && !str.includes("Z")) {
    str += "Z";
  }
  const t = new Date(str).getTime();
  if (Number.isNaN(t)) return "";
  const s = Math.max(1, Math.floor((Date.now() - t) / 1000));
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d}d ago`;
  return new Date(str).toLocaleDateString();
}

const AGENT_ROWS = [
  { name: "Research", desc: "Deep research, evidence and structured answers", path: "/research" },
  { name: "Shopping", desc: "Compare products and prices", path: "/shopping" },
  { name: "Jobs", desc: "Find and monitor opportunities", path: "/jobs" },
  { name: "Flights", desc: "Fare search across dates and airlines", path: "/flights" },
  { name: "Hotels", desc: "Stays, rooms and nightly rates", path: "/hotels" },
  { name: "Trips", desc: "Full itinerary: flights, hotels, plans", path: "/trips" },
];

// Rotating hero lines: 4 time slots x 6 messages. Picked deterministically
// by day-of-year — stable all day, fresh every morning. No backend needed.
const GREETINGS = {
  morning: [
    { greet: "Good morning", sub: "What are we hunting today — flights, hotels or deep research?" },
    { greet: "Morning", sub: "Fresh day, fast answers. Where should we start?" },
    { greet: "Good morning", sub: "Coffee's on you, answers are on me — what's first?" },
    { greet: "Rise and shine", sub: "What are you looking for this morning?" },
    { greet: "Good morning", sub: "Big plans today? Point me at one and let's go." },
    { greet: "Morning", sub: "Your agents are warmed up — give them something to do." },
  ],
  afternoon: [
    { greet: "Good afternoon", sub: "What can I help you with today?" },
    { greet: "Good afternoon", sub: "Midday momentum — what are we solving next?" },
    { greet: "Hey there", sub: "Afternoon slump? Hand me a task and keep moving." },
    { greet: "Good afternoon", sub: "Quick ask or deep dive — I'm ready either way." },
    { greet: "Welcome back", sub: "Anything pending from this morning to finish?" },
    { greet: "Good afternoon", sub: "Trips, research, shopping — pick your lane." },
  ],
  evening: [
    { greet: "Good evening", sub: "Winding down or gearing up — what do you need?" },
    { greet: "Good evening", sub: "One good answer before dinner — what's the question?" },
    { greet: "Evening", sub: "Planning something fun tonight? Start here." },
    { greet: "Good evening", sub: "What are you looking for this evening?" },
    { greet: "Welcome back", sub: "Let's close out the day strong — what's left?" },
    { greet: "Good evening", sub: "Research, travel, shopping — all yours till late." },
  ],
  night: [
    { greet: "Burning midnight oil", sub: "Quiet hours, fast answers — what do you need?" },
    { greet: "Up late", sub: "No judgment — what's on your mind?" },
    { greet: "Good night", sub: "One last thing before you log off?" },
    { greet: "Night owl mode", sub: "Tomorrow's plans start tonight. Shoot." },
    { greet: "Still awake", sub: "Quick one or a rabbit hole — your call." },
    { greet: "Good night", sub: "Dream trips count too — where to?" },
  ],
};

function greeting() {
  const now = new Date();
  const h = now.getHours();
  const slot = h >= 5 && h < 12 ? "morning" : h >= 12 && h < 17 ? "afternoon" : h >= 17 && h < 22 ? "evening" : "night";
  const list = GREETINGS[slot];
  // Day-of-year keeps it stable all day, fresh every morning.
  const start = new Date(now.getFullYear(), 0, 0);
  const day = Math.floor((now - start) / 86400000);
  return list[day % list.length];
}

function maskEmail(email = "") {
  const [u, d] = email.split("@");
  if (!u || !d) return email;
  return `${u[0]}***@${d}`;
}

export default function Home() {
  const navigate = useNavigate();
  const inputRef = useRef(null);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [netDown, setNetDown] = useState(false);
  const [active, setActive] = useState("Home");
  const [menu, setMenu] = useState(false);
  const [profile, setProfile] = useState(false);
  const [agent, setAgent] = useState(DEFAULT_AGENT_ID);
  const [query, setQuery] = useState("");
  // Real universal-layer state. `thinking` while the LLM decides, `reply` for
  // the Assistant's inline answer (it has no page to navigate to).
  const [thinking, setThinking] = useState(false);
  const [reply, setReply] = useState(null); // { q, text }
const [routeError, setRouteError] = useState(null);
const [activity, setActivity] = useState([]);
  // Set when the router picked an agent but a required field was missing. The
  // asker renders in the chat area instead of navigating, so the user never
  // reaches a form they would only have to come back from.
  const [pendingRoute, setPendingRoute] = useState(null);
  const [mailEnabled, setMailEnabled] = useState(false);
  const [verifyDismissed, setVerifyDismissed] = useState(readVerifySkipped);
  const [verifyOpen, setVerifyOpen] = useState(false);

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
        setMailEnabled(Boolean(data.verification_available));
        setLoading(false);
        // Jobs is in this list too — omitting it was why job searches never
        // appeared in Recent activity.
        Promise.all([
          authFetch("/api/research/history?limit=5").then((h) => h && !h.unauthorized && !h.networkError ? h.json().catch(() => ({})) : {}),
          authFetch("/api/shopping/history?limit=5").then((h) => h && !h.unauthorized && !h.networkError ? h.json().catch(() => ({})) : {}),
          authFetch("/api/flights/history?limit=5").then((h) => h && !h.unauthorized && !h.networkError ? h.json().catch(() => ({})) : {}),
          authFetch("/api/hotels/history?limit=5").then((h) => h && !h.unauthorized && !h.networkError ? h.json().catch(() => ({})) : {}),
          authFetch("/api/trips/history?limit=5").then((h) => h && !h.unauthorized && !h.networkError ? h.json().catch(() => ({})) : {}),
          authFetch("/api/jobs/history?limit=5").then((h) => h && !h.unauthorized && !h.networkError ? h.json().catch(() => ({})) : {}),
        ])
          .then(([rd, sd, fd, hd, td, jd]) => {
            const rItems = (rd.items || []).map((a) => ({ ...a, agent: "Research" }));
            const sItems = (sd.items || []).map((a) => ({
              session_id: a.session_id,
              query: a.title || a.query,
              updated_at: a.last_search_at || a.updated_at,
              status: "completed",
              agent: "Shopping",
            }));
            const fItems = (fd.items || []).map((a) => ({
              session_id: a.session_id,
              query: a.title || a.query,
              updated_at: a.last_search_at || a.updated_at,
              status: "completed",
              agent: "Flights",
            }));
            const hItems = (hd.items || []).map((a) => ({
              session_id: a.session_id,
              query: a.title || a.query,
              updated_at: a.last_search_at || a.updated_at,
              status: "completed",
              agent: "Hotels",
            }));
            const tItems = (td.items || []).map((a) => ({
              session_id: a.session_id,
              query: a.title || a.query,
              updated_at: a.updated_at,
              status: a.status === "ready" ? "completed" : a.status,
              agent: "Trips",
            }));
            const jItems = (jd.items || []).map((a) => ({
              session_id: a.session_id,
              query: a.title || a.query,
              updated_at: a.last_search_at || a.updated_at,
              status: "completed",
              agent: "Jobs",
            }));
            // Most recent first across ALL agents — previously slice(0, 5)
            // on research-first concatenation always buried travel items.
            const timeOf = (a) => {
              const t = new Date(a.updated_at || 0).getTime();
              return Number.isNaN(t) ? 0 : t;
            };
            const all = [...rItems, ...sItems, ...fItems, ...hItems, ...tItems, ...jItems];
            all.sort((a, b) => timeOf(b) - timeOf(a));
            setActivity(all.slice(0, 6));
          })
          .catch(() => {});
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

  const skipVerify = () => {
    writeVerifySkipped();
    setVerifyDismissed(true);
  };

  // Escape hatch for "Skip for now": the banner is gone but verification is
  // still possible from the profile menu, so the skip is never a dead end.
  const startVerify = () => {
    clearVerifySkipped();
    setVerifyDismissed(false);
    setProfile(false);
    setVerifyOpen(true);
  };

  const onVerified = () => {
    setUser((u) => (u ? { ...u, email_verified: true } : u));
    setVerifyOpen(false);
  };

  const showVerifyBanner = Boolean(
    user && !user.email_verified && mailEnabled && !verifyDismissed && !verifyOpen
  );

  const submit = (e) => {
    e.preventDefault();
    const q = query.trim();
    if (!q || thinking) return;
    // A chosen agent just goes to its own workspace. No keyword sniffing here:
    // Flights / Hotels / Trips used to be lumped into one "Travel" pill that
    // guessed between them, so picking Travel for a hotel search could land on
    // a full itinerary plan instead.
    const chosen = AGENT_BY_ID[agent];
    if (chosen?.path) {
      navigate(`${chosen.path}?q=${encodeURIComponent(q)}`);
      return;
    }

    // ---- Auto: the universal layer decides -------------------------------
    // The LLM picks ONE specialist and pre-extracts its form fields. It does
    // not run anything: we navigate, the destination pre-fills its form, and
    // the user presses Search themselves. A greeting gets an inline reply
    // instead, because the Assistant has no page.
    setThinking(true);
    setRouteError(null);
    setReply(null);
    routeIntent(q)
      .then((d) => {
        if (d.unauthorized) {
          navigate("/login", { replace: true });
          return;
        }
        if (d.networkError) throw new Error("Cannot reach the server. Is the backend running?");
        if (d.agent === "assistant") {
          return askAssistant(q).then((a) => {
            if (a.unauthorized) {
              navigate("/login", { replace: true });
              return;
            }
            if (a.networkError) throw new Error("Cannot reach the server. Is the backend running?");
            setReply({ q, text: a.reply || "I'm not sure how to answer that right now." });
          });
        }
        // Surface the real reason instead of a generic message: an unknown
        // agent, a missing path, or a shape change all land here.
        if (!d.path) {
          throw new Error(
            d.agent
              ? `The router picked "${d.agent}" but gave no destination for it.`
              : "The router did not choose an agent. Please try rephrasing."
          );
        }
        // Ask before navigating when a required field is missing, so the user
        // answers in their own words instead of landing on a half-filled form.
        // The router told us exactly what it could not get.
        //
        // No repeat-ask guard here. There used to be one, because answering
        // re-routed the combined text through the model and could come back
        // still missing something - route, ask, answer, ask again. handleAnswers
        // merges and navigates directly now, so that loop cannot happen, and the
        // guard only did harm: dismissing the question added the query to a Set
        // that lived for the page, so the same question never asked again and the
        // user was silently dropped onto a form whose Search button was disabled.
        const missing = d.receipt?.missing || [];
        if (missing.length > 0) {
          setPendingRoute({ route: d, q, agent: d.agent });
          return;
        }

        // `state` (not the URL) carries the pre-extracted fields. It dies with
        // the navigation, so a refresh falls back to the page's own parser
        // instead of re-applying stale values.
        //
        // autoRun fires only when nothing was missing. That is the whole
        // difference between an agent and a redirect.
        navigate(`${d.path}?q=${encodeURIComponent(q)}`, {
          state: {
            prefill: {
              agent: d.agent,
              query: q,
              fields: d.fields || {},
              receipt: d.receipt || null,
              reason: d.reason || "",
              confidence: typeof d.confidence === "number" ? d.confidence : null,
              autoRun: missing.length === 0,
            },
          },
        });
      })
      .catch((err) => {
        setRouteError(
          err.code === "unauthorized"
            ? "Session expired. Please sign in again."
            : err.message || "Could not reach the assistant."
        );
      })
      .finally(() => setThinking(false));
  };

  /**
   * Answers are merged straight into the fields the router already returned and
   * the user is handed over immediately.
   *
   * This used to re-route the combined text through the model, which cost a
   * second 1.5-3.6s call after the user had already answered - the single worst
   * pause in the flow, since it happened while they were waiting on nothing.
   * Re-routing was only buying normalisation, and the asker needs none: date
   * fields use <input type="date"> so they are already YYYY-MM-DD.
   *
   * Correctness is not left to the merge. The destination form's own `valid`
   * expression is the final gate before any search fires, so an answer that
   * cannot be used (a budget of "mid-range") leaves the form unsubmittable
   * rather than triggering a run on junk.
   */
  const handleAnswers = (answerLines) => {
    if (!pendingRoute) return;
    const { route, q, agent } = pendingRoute;

    const answers = {};
    for (const line of String(answerLines || "").split("\n")) {
      const i = line.indexOf(":");
      if (i > 0) answers[line.slice(0, i).trim()] = line.slice(i + 1).trim();
    }

    const fields = mergeFields(route.fields || {}, answers);
    const answered = Object.keys(answers);
    const receipt = { ...(route.receipt || {}) };

    // Keep the receipt honest - it would otherwise still say the date is needed
    // on the page the user is about to land on.
    if (Array.isArray(receipt.missing)) {
      receipt.missing = receipt.missing.filter((f) => !answered.includes(f));
    }
    receipt.understood = { ...(receipt.understood || {}), ...answers };

    setPendingRoute(null);
    navigate(`${route.path}?q=${encodeURIComponent(q)}`, {
      state: {
        prefill: {
          agent,
          query: q,
          fields,
          receipt: Object.keys(receipt).length ? receipt : null,
          reason: route.reason || "",
          confidence: typeof route.confidence === "number" ? route.confidence : null,
          autoRun: true,
        },
      },
    });
  };

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
              <button
                key={n}
                className={`dash-navlink${active === n ? " active" : ""}`}
                onClick={() => {
                  setMenu(false);
                  // Same lookup as submit(): one source of truth for paths.
                  const target = NAV_PATH[n];
                  if (target) {
                    navigate(target);
                    return;
                  }
                  setActive(n);
                }}
              >
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
                {mailEnabled && !user.email_verified && (
                  <button className="dash-menuitem" onClick={startVerify}>
                    Verify email
                  </button>
                )}
                <div className="dash-menudiv" />
                <button className="dash-menuitem" onClick={logout}>Sign out</button>
              </div>
            )}
          </div>
          <button className="dash-burger" onClick={() => setMenu((m) => !m)}><MenuIcon /></button>
        </div>
      </header>

      <main className="dash-main dash-wide">
        {showVerifyBanner && (
          <VerifyBanner
            email={user.email}
            onVerify={() => setVerifyOpen(true)}
            onSkip={skipVerify}
          />
        )}

        <section className="dash-hero">
          <h1>{greeting().greet}, {firstName}</h1>
          <p className="auth-sub">{greeting().sub}</p>
          <form onSubmit={submit} className="dash-ask">
            {/* Agent lives inside the input bar. Custom, not a native <select>:
                the OS paints that popup itself and it ignores the dark theme. */}
            <AgentSelect
              value={agent}
              options={AGENT_OPTIONS}
              onChange={setAgent}
              disabled={thinking}
            />
            <input
              ref={inputRef}
              placeholder="Ask anything..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              disabled={thinking}
            />
            <button type="submit" aria-label="Send" disabled={thinking || !query.trim()}>
              {thinking ? <span className="spinner-small" /> : <SendIcon />}
            </button>
          </form>
          <p className="dash-hint">Ask anything. I&apos;ll figure out which AI agent can help.</p>

          {/* The conversation sits directly under the input, not at the bottom
              of the page. It is the answer to what the user just typed, so it
              belongs next to the box they typed it in. */}
          {(thinking || reply || routeError || pendingRoute) && (
            <div className="dash-chat" role="status" aria-live="polite">
              <div className="dash-chat-row dash-chat-you">
                <span className="dash-chat-bubble">
                  {pendingRoute ? pendingRoute.q : reply ? reply.q : query.trim()}
                </span>
              </div>

              {thinking && (
                <div className="dash-chat-row">
                  <span className="dash-chat-bubble dash-chat-bubble-bot dash-chat-bubble-thinking">
                    <span className="dash-chat-dots">
                      <i /><i /><i />
                    </span>
                    <span className="dash-thinking-label">{thinkingLabel(query)}</span>
                  </span>
                </div>
              )}

              {routeError && (
                <div className="dash-chat-row">
                  <span className="dash-chat-bubble dash-chat-bubble-bot dash-chat-bubble-err">
                    {routeError}
                  </span>
                </div>
              )}

              {reply && (
                <div className="dash-chat-row">
                  <span className="dash-chat-bubble dash-chat-bubble-bot">{reply.text}</span>
                </div>
              )}

              {/* The router understood most of it but a required field was
                  missing. Ask here rather than handing over a form that is
                  already blocked. */}
              {pendingRoute && !thinking && (
                <Clarifying
                  questions={asksFor(pendingRoute.route?.receipt?.missing || [])}
                  message={`I can take this to ${
                    AGENT_LABELS[pendingRoute.agent] || pendingRoute.agent
                  } — I just need a couple of details:`}
                  loading={thinking}
                  submitLabel="Run it"
                  onAnswer={handleAnswers}
                />
              )}

              {!thinking && (reply || routeError || pendingRoute) && (
                <button
                  type="button"
                  className="dash-chat-close"
                  onClick={() => { setReply(null); setRouteError(null); setPendingRoute(null); }}
                  aria-label="Dismiss reply"
                  title="Dismiss"
                >
                  ×
                </button>
              )}
            </div>
          )}

          {/* No pill row: the agent is the dropdown inside the input bar. */}
          <div className="dash-suggest">
            <p className="dash-sect-label">Try asking</p>
            <div className="dash-suggest-grid">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s.text}
                  type="button"
                  className="dash-suggest-card"
                  onClick={() => {
                    // Prefill only. This must never run the agent — the user
                    // still has to press Send. type="button" keeps it that way
                    // even if this markup ever ends up inside a <form>.
                    setQuery(s.text);
                    setAgent(s.agent);
                    if (inputRef.current) inputRef.current.focus();
                  }}
                >
                  {/* s.agent is an id now ("flights"), so show the label. */}
                  <strong>{AGENT_BY_ID[s.agent]?.label || s.agent}</strong>
                  <span>&ldquo;{s.text}&rdquo;</span>
                </button>
              ))}
            </div>
          </div>
        </section>

        {/* Assistant reply and the real routing state. Replaces the old fake
            "connects here soon" step animation. */}
        <section>
          <p className="dash-sect-label">Recent activity</p>
          <div className="dash-activity">
            {activity.length === 0 && (
              <div className="dash-act-card">
                <strong>Research</strong>
                <span className="dash-act-title">Your workspace is ready — start by asking something.</span>
                <div className="dash-act-foot">
                  <span>no history yet</span>
                  <button className="auth-link" onClick={() => navigate("/research")}>Ask something →</button>
                </div>
              </div>
            )}
            {activity.map((a) => (
              <div className="dash-act-card" key={`${a.agent || "Research"}-${a.session_id}`}>
                <strong>{a.agent || "Research"}</strong>
                <span className="dash-act-title">{a.query}</span>
                <div className="dash-act-foot">
                  <span>{a.status === "running" ? "working…" : a.status === "awaiting_input" ? "input needed" : timeAgo(a.updated_at)}</span>
                  <button
                    className="auth-link"
                    onClick={() => navigate(`${ACTIVITY_PATH[a.agent] || "/research"}/${a.session_id}`)}
                  >Open →</button>
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
                <button className="auth-link" onClick={() => navigate(a.path)}>Explore →</button>
              </div>
            ))}
          </div>
        </section>

        <section>
          <p className="dash-sect-label">Job alerts</p>
          <p className="dash-sect-sub">Get daily or weekly alerts for roles and locations you pick.</p>
          <div style={{ display: "flex", gap: ".6rem", flexWrap: "wrap" }}>
            <button className="btn-google" style={{ maxWidth: 220, height: 44 }} onClick={() => navigate("/jobs")}>
              <BriefcaseIcon size={15} /> Browse jobs
            </button>
            <button className="auth-link" style={{ alignSelf: "center" }} onClick={() => navigate("/jobs")}>
              Create job alert →
            </button>
          </div>
        </section>
      </main>

      {verifyOpen && user && (
        <OtpModal
          email={user.email}
          onVerified={onVerified}
          onClose={() => setVerifyOpen(false)}
        />
      )}
    </div>
  );
}
