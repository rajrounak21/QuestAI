import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { researchApi, timeAgo } from "./api";
import { getToken } from "../auth/api";
import { SendIcon } from "../auth/components/icons";
import "./Research.css";

const POLL_MS = 3000;
const POLL_MAX = 40;
const PIPE_STEPS = ["Planning", "Searching", "Synthesizing", "Validating"];

function statusDot(status) {
  if (status === "running") return <span className="rs-dot rs-dot-run" />;
  if (status === "failed") return <span className="rs-dot rs-dot-fail" />;
  return <span className="rs-dot rs-dot-done" />;
}

// evidence_ref (ev_001) -> 1-based number from report.sources order
function buildRefNumbers(report, evidence) {
  const sources = report?.sources || [];
  const urlToIdx = new Map();
  sources.forEach((s, i) => {
    if (s.url && !urlToIdx.has(s.url)) urlToIdx.set(s.url, i + 1);
  });
  const evById = new Map((evidence || []).map((e) => [e.id, e]));
  return (ref) => {
    const ev = evById.get(ref);
    const url = ev?.source?.url;
    return (url && urlToIdx.get(url)) || ref.replace("ev_", "");
  };
}

export default function Research() {
  const navigate = useNavigate();
  const { sessionId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();

  const [sessions, setSessions] = useState([]);
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [input, setInput] = useState("");
  const [running, setRunning] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [confirm, setConfirm] = useState(null); // { proposed }
  const [inspector, setInspector] = useState(null); // evidence item
  const [openFindings, setOpenFindings] = useState({});
  const [panelOpen, setPanelOpen] = useState(false);
  const [notice, setNotice] = useState("");

  const pollRef = useRef(null);
  const autoRunRef = useRef(false);
  const elapsedRef = useRef(null);

  const loadSessions = async () => {
    try {
      const data = await researchApi.history(30);
      setSessions(data.items || []);
    } catch {
      /* sidebar stays empty, page still works */
    }
  };

  const stopPoll = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = null;
    if (elapsedRef.current) clearInterval(elapsedRef.current);
    elapsedRef.current = null;
  };

  const pollUntilDone = (id) => {
    stopPoll();
    setRunning(true);
    setElapsed(0);
    elapsedRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
    let tries = 0;
    pollRef.current = setInterval(async () => {
      tries += 1;
      try {
        const d = await researchApi.getSession(id);
        setDoc(d);
        if (d.status !== "running" || tries >= POLL_MAX) {
          stopPoll();
          setRunning(false);
          loadSessions();
          if (tries >= POLL_MAX && d.status === "running") {
            setNotice("Still working — refresh in a bit. The run continues on the server.");
          }
        }
      } catch (e) {
        if (e.code === "unauthorized") {
          stopPoll();
          setRunning(false);
          navigate("/login", { replace: true });
        }
      }
    }, POLL_MS);
  };

  const submit = async (rawQuery, opts = {}) => {
    const query = (rawQuery || "").trim();
    if (!query || running) return;
    setNotice("");
    setInspector(null);
    setConfirm(null);
    const targetId = opts.force_new ? undefined : sessionId;
    try {
      const res = await researchApi.run({
        query,
        session_id: targetId,
        force_new: opts.force_new,
        force_continue: opts.force_continue,
      });
      if (res.needs_confirm) {
        setConfirm({ proposed: res.proposed_new_goal || query });
        return;
      }
      setInput("");
      if (!targetId || res.session_id !== targetId) {
        navigate(`/research/${res.session_id}`, { replace: !targetId });
      }
      setPanelOpen(false);
      pollUntilDone(res.session_id);
    } catch (e) {
      if (e.code === "unauthorized") {
        navigate("/login", { replace: true });
        return;
      }
      if (e.code === 409 && e.detail?.session_id) {
        pollUntilDone(e.detail.session_id); // already running — attach to it
        return;
      }
      setNotice(e.message || "Research failed to start.");
    }
  };

  // auth guard + sidebar
  useEffect(() => {
    if (!getToken()) {
      navigate("/login", { replace: true });
      return;
    }
    loadSessions().finally(() => setLoading(false));
    return stopPoll;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // load current session doc
  useEffect(() => {
    if (!sessionId) {
      setDoc(null);
      setRunning(false);
      stopPoll();
      return;
    }
    let alive = true;
    researchApi
      .getSession(sessionId)
      .then((d) => {
        if (!alive) return;
        setDoc(d);
        if (d.status === "running") pollUntilDone(sessionId);
        else {
          setRunning(false);
          stopPoll();
        }
      })
      .catch(() => {
        if (alive) setNotice("Could not load this session.");
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  // auto-run ?q= once (StrictMode-safe)
  useEffect(() => {
    const q = searchParams.get("q");
    if (!q || autoRunRef.current || sessionId) return;
    autoRunRef.current = true;
    setSearchParams({}, { replace: true });
    submit(q);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, sessionId]);

  const newChat = () => {
    stopPoll();
    setRunning(false);
    setDoc(null);
    setInput("");
    setConfirm(null);
    setInspector(null);
    setNotice("");
    setPanelOpen(false);
    navigate("/research");
  };

  const report = doc?.report || null;
  const refNum = buildRefNumbers(report, doc?.evidence);
  const quality = report?.validation_notes?.overall_quality;

  const toggleFinding = (i) => setOpenFindings((m) => ({ ...m, [i]: m[i] === false }));

  return (
    <div className="rs">
      {/* report workspace */}
      <main className="rs-main">
        <header className="rs-top">
          <Link to="/home" className="rs-back" title="Back to workspace">
            ←
          </Link>
          <div className="rs-title">
            <h1>{doc?.query || "Research"}</h1>
            {doc && (
              <span className="rs-meta">
                {statusDot(doc.status)} {doc.status}
                {quality && quality !== "unknown" && (
                  <span className="rs-quality"> · {quality} ✓</span>
                )}
                <span className="rs-meta-time"> · {timeAgo(doc.updated_at)}</span>
              </span>
            )}
          </div>
          <div className="rs-top-actions">
            <button className="rs-new-btn" onClick={newChat}>
              + New
            </button>
            <button className="rs-sess-btn" onClick={() => setPanelOpen(true)}>
              Sessions
            </button>
          </div>
        </header>

        {notice && <p className="rs-notice">{notice}</p>}

        {running && (
          <section className="rs-pipe" aria-live="polite">
            {PIPE_STEPS.map((s, i) => (
              <span key={s} className="rs-pipe-step">
                <span className="rs-pulse" style={{ animationDelay: `${i * 0.25}s` }} />
                {s}
              </span>
            ))}
            <span className="rs-pipe-time">{elapsed}s · input locked until done</span>
          </section>
        )}

        {loading ? (
          <p className="rs-loading">Loading workspace...</p>
        ) : !doc && !running ? (
          <section className="rs-empty">
            <h2>Your research desk is ready.</h2>
            <p className="auth-sub">Ask a research question — answers come with evidence and sources.</p>
            <div className="rs-empty-grid">
              {["Compare RAG evaluation frameworks", "MIRAGE dataset for RAG evaluation", "TREC 2025 RAG track methods"].map(
                (q) => (
                  <button key={q} className="rs-empty-card" onClick={() => submit(q)}>
                    “{q}”
                  </button>
                )
              )}
            </div>
          </section>
        ) : (
          doc && (
            <article className="rs-doc">
              {doc.conversation?.length > 1 && (
                <section className="rs-thread">
                  <p className="rs-sect">Thread</p>
                  {doc.conversation.slice(0, -1).map((t, i) => (
                    <p key={i} className="rs-thread-q">
                      <strong>Q{i + 1}.</strong> {(t.user || "").slice(0, 160)}
                    </p>
                  ))}
                </section>
              )}

              {report?.executive_summary && (
                <section>
                  <p className="rs-sect">Executive summary</p>
                  <p className="rs-summary">{report.executive_summary}</p>
                </section>
              )}

              {(report?.findings || []).length > 0 && (
                <section>
                  <p className="rs-sect">Findings</p>
                  {(report.findings || []).map((f, i) => {
                    const open = openFindings[i] !== false;
                    return (
                      <div key={i} className="rs-finding">
                        <button className="rs-finding-head" onClick={() => toggleFinding(i)}>
                          <span>
                            {i + 1}. {f.title}
                          </span>
                          <span className="rs-caret">{open ? "–" : "+"}</span>
                        </button>
                        {open && (
                          <div className="rs-finding-body">
                            <p>
                              {f.explanation}{" "}
                              {(f.evidence_refs || []).map((r) => (
                                <button
                                  key={r}
                                  className="rs-ref"
                                  title="View evidence"
                                  onClick={() =>
                                    setInspector((doc.evidence || []).find((e) => e.id === r) || null)
                                  }
                                >
                                  [{refNum(r)}]
                                </button>
                              ))}
                            </p>
                            {(f.sources || []).map(
                              (s) =>
                                s.url && (
                                  <a
                                    key={s.url}
                                    className="rs-src"
                                    href={s.url}
                                    target="_blank"
                                    rel="noreferrer"
                                  >
                                    {s.title} <span>({s.source_type})</span>
                                  </a>
                                )
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </section>
              )}

              {report?.comparison && (
                <section>
                  <p className="rs-sect">Comparison</p>
                  <p>{report.comparison}</p>
                </section>
              )}
              {report?.recent_developments && (
                <section>
                  <p className="rs-sect">Recent developments</p>
                  <p>{report.recent_developments}</p>
                </section>
              )}
              {report?.limitations && (
                <section>
                  <p className="rs-sect">Limitations</p>
                  <p>{report.limitations}</p>
                </section>
              )}

              {(report?.sources || []).length > 0 && (
                <section>
                  <p className="rs-sect">Sources ({report.sources.length})</p>
                  <ol className="rs-sources">
                    {report.sources.map((s, i) => (
                      <li key={`${s.url}-${i}`}>
                        <a href={s.url} target="_blank" rel="noreferrer">
                          {s.title || s.url}
                        </a>{" "}
                        <span>({s.source_type})</span>
                      </li>
                    ))}
                  </ol>
                </section>
              )}

              {doc.status === "failed" && (
                <p className="rs-notice">
                  This run failed{doc.error ? `: ${doc.error}` : "."} Ask again to retry.
                </p>
              )}
            </article>
          )
        )}

        <form
          className="rs-ask"
          onSubmit={(e) => {
            e.preventDefault();
            submit(input);
          }}
        >
          <input
            placeholder={running ? "Researching — input locked..." : "Ask a follow-up or start a topic..."}
            value={input}
            disabled={running}
            onChange={(e) => setInput(e.target.value)}
          />
          <button type="submit" aria-label="Send" disabled={running || !input.trim()}>
            <SendIcon />
          </button>
        </form>
      </main>

      {/* sessions — right on desktop, slide-over on mobile */}
      <aside className={`rs-sessions${panelOpen ? " open" : ""}`} aria-label="Sessions">
        <div className="rs-sess-head">
          <button className="auth-link" onClick={newChat}>
            + New
          </button>
        </div>
        <div className="rs-sess-list">
          {sessions.length === 0 && <p className="rs-sess-empty">No sessions yet.</p>}
          {sessions.map((s) => (
            <button
              key={s.session_id}
              className={`rs-sess${s.session_id === sessionId ? " active" : ""}`}
              onClick={() => {
                setPanelOpen(false);
                navigate(`/research/${s.session_id}`);
              }}
            >
              {statusDot(s.status)}
              <span className="rs-sess-q">{s.query}</span>
              <span className="rs-sess-t">{timeAgo(s.updated_at)}</span>
            </button>
          ))}
        </div>
      </aside>
      {panelOpen && <div className="rs-scrim" onClick={() => setPanelOpen(false)} />}

      {/* evidence inspector overlay */}
      {inspector && (
        <div className="rs-insp-wrap">
          <div className="rs-insp">
            <div className="rs-insp-head">
              <strong>{inspector.id}</strong>
              <button className="auth-link" onClick={() => setInspector(null)}>
                Close ✕
              </button>
            </div>
            <p className="rs-insp-claim">“{inspector.claim}”</p>
            <p className="rs-insp-sup">{inspector.supporting_text}</p>
            {inspector.source?.url && (
              <a href={inspector.source.url} target="_blank" rel="noreferrer" className="rs-src">
                {inspector.source.title} <span>({inspector.source.source_type})</span>
              </a>
            )}
          </div>
        </div>
      )}

      {/* topic-split confirm */}
      {confirm && (
        <div className="rs-insp-wrap">
          <div className="rs-insp">
            <p className="rs-sect">New research topic?</p>
            <p>
              Current: <strong>{doc?.query || "this session"}</strong>
            </p>
            <p>
              Asked: <strong>{confirm.proposed}</strong>
            </p>
            <div className="rs-confirm-row">
              <button
                className="btn-primary"
                style={{ maxWidth: 200 }}
                onClick={() => submit(confirm.proposed, { force_new: true })}
              >
                Start new
              </button>
              <button
                className="btn-google"
                style={{ maxWidth: 200 }}
                onClick={() => submit(input || confirm.proposed, { force_continue: true })}
              >
                Continue here
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
