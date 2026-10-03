import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { researchApi, timeAgo } from "./api";
import { getToken } from "../auth/api";
import { useRouterPrefill } from "../src/shared/useRouterPrefill";
import { SendIcon } from "../auth/components/icons";
import "./Research.css";

const POLL_MS = 1500;
const POLL_MAX = 40;
const STAGES = [
  { key: "planning", label: "Planning" },
  { key: "searching", label: "Searching" },
  { key: "synthesizing", label: "Synthesizing" },
  { key: "validating", label: "Validating" },
];

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
  const num = (ref) => {
    const ev = evById.get(ref);
    const url = ev?.source?.url;
    return (url && urlToIdx.get(url)) || ref.replace("ev_", "");
  };
  return { num, has: (ref) => evById.has(ref) };
}

// rich text: (ev_012)/ev_012 -> clickable evidence refs, `code` inline tags & **bold** parsing
function renderRich(text, refs, onRef) {
  if (!text) return null;

  // Split by evidence refs first (ev_012)
  const parts = String(text).split(/(\(ev_\d+\)|\bev_\d+\b)/g);

  return parts.map((p, i) => {
    const m = p.match(/^\(?(ev_\d+)\)?$/);
    if (m && refs?.has && refs.has(m[1])) {
      return (
        <button key={i} className="rs-ref" title="View evidence" onClick={() => onRef(m[1])}>
          [{refs.num(m[1])}]
        </button>
      );
    }

    // Split by inline code backticks `code` or single-quoted identifiers 'code'
    const codeTokens = p.split(/(`[^`]+`|'[^']{2,35}')/g);
    return codeTokens.map((cToken, cIdx) => {
      // Inline backtick code: `Retriever.evaluate`
      if (cToken.startsWith("`") && cToken.endsWith("`") && cToken.length > 2) {
        return (
          <code key={`${i}-${cIdx}`} className="rs-inline-code">
            {cToken.slice(1, -1)}
          </code>
        );
      }
      // Single quoted code identifiers: 'Retriever.evaluate' or 'openai-evals'
      if (
        cToken.startsWith("'") &&
        cToken.endsWith("'") &&
        cToken.length > 2 &&
        /^[A-Za-z0-9_.\-@ ()]+$/.test(cToken.slice(1, -1)) &&
        !cToken.includes(" ")
      ) {
        return (
          <code key={`${i}-${cIdx}`} className="rs-inline-code">
            {cToken.slice(1, -1)}
          </code>
        );
      }

      // Parse **bold** markdown tokens inside text
      const boldTokens = cToken.split(/(\*\*[^*]+\*\*)/g);
      return boldTokens.map((sub, sIdx) => {
        if (sub.startsWith("**") && sub.endsWith("**") && sub.length > 4) {
          return <strong key={`${i}-${cIdx}-${sIdx}`}>{sub.slice(2, -2)}</strong>;
        }
        return <span key={`${i}-${cIdx}-${sIdx}`}>{sub}</span>;
      });
    });
  });
}

function renderMarkdown(text, refs, onRef) {
  if (!text) return null;

  // Split text into blocks by double newlines or table blocks
  const rawBlocks = String(text).split(/\n{2,}/g);

  return rawBlocks.map((block, bIdx) => {
    const trimmed = block.trim();
    if (!trimmed) return null;

    // 1. Check for Markdown Table syntax: | col1 | col2 |\n|---|---|
    const lines = trimmed.split("\n").map((l) => l.trim()).filter(Boolean);
    if (lines.length >= 2 && lines[0].includes("|") && lines[1].includes("|") && lines[1].includes("-")) {
      const headers = lines[0].split("|").map((cell) => cell.trim()).filter((c) => c.length > 0);
      const dataRows = lines.slice(2).map((row) =>
        row.split("|").map((cell) => cell.trim()).filter((c) => c.length > 0)
      );

      return (
        <div key={bIdx} className="rs-table-wrapper">
          <table className="rs-table">
            <thead>
              <tr>
                {headers.map((h, hIdx) => (
                  <th key={hIdx}>{renderRich(h, refs, onRef)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {dataRows.map((row, rIdx) => (
                <tr key={rIdx}>
                  {row.map((cell, cIdx) => (
                    <td key={cIdx}>{renderRich(cell, refs, onRef)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }

    // 2. Check for Bullet or Numbered Lists
    if (lines.length > 1 && lines.every((l) => l.startsWith("- ") || l.startsWith("* ") || /^\d+\.\s/.test(l))) {
      return (
        <ul key={bIdx} className="rs-list">
          {lines.map((l, lIdx) => {
            const cleanLine = l.replace(/^[-*]\s+/, "").replace(/^\d+\.\s+/, "");
            return <li key={lIdx}>{renderRich(cleanLine, refs, onRef)}</li>;
          })}
        </ul>
      );
    }

    // 3. Check for Headings
    if (trimmed.startsWith("### ")) {
      return <h4 key={bIdx} className="rs-md-h4">{renderRich(trimmed.replace(/^###\s+/, ""), refs, onRef)}</h4>;
    }
    if (trimmed.startsWith("## ")) {
      return <h3 key={bIdx} className="rs-md-h3">{renderRich(trimmed.replace(/^##\s+/, ""), refs, onRef)}</h3>;
    }

    // 4. Default Paragraph
    return (
      <p key={bIdx} className="rs-para">
        {renderRich(trimmed, refs, onRef)}
      </p>
    );
  });
}

function cleanAssistantAnswer(text) {
  if (!text) return "";
  return text
    .replace(/^#\s+Research Report\n?/gi, "")
    .replace(/\*\*Goal:\*\*[^\n]*\n?/gi, "")
    .replace(/^##\s+/gm, "")
    .trim();
}

function runSeconds(doc) {
  const raw = doc?.started_at || doc?.created_at;
  const t = parseIso(raw);
  if (!t) return 0;
  return Math.max(0, Math.floor((Date.now() - t) / 1000));
}

function fmtElapsed(total) {
  const s = Math.max(0, Math.floor(total || 0));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ${String(s % 60).padStart(2, "0")}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${String(m % 60).padStart(2, "0")}m`;
}

function parseIso(iso) {
  if (!iso) return 0;
  let str = String(iso);
  if (!str.endsWith("Z") && !str.includes("+") && !str.includes("Z")) {
    str += "Z";
  }
  const t = new Date(str).getTime();
  return Number.isNaN(t) ? 0 : t;
}

function isFresh(doc) {
  const raw = doc?.progress?.at || doc?.updated_at || doc?.started_at;
  const t = parseIso(raw);
  if (!t) return false;
  return Date.now() - t < 120000;
}

// new-chat icon (ChatGPT-style square-pen) — exact reference SVG
function NewChatSvg() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" role="img" aria-label="New chat">
      <path d="M12 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.375 2.625a1 1 0 0 1 3 3l-9.013 9.014a2 2 0 0 1-.853.505l-2.873.84a.5.5 0 0 1-.62-.62l.84-2.873a2 2 0 0 1 .506-.852z" />
    </svg>
  );
}

function PanelSvg() {

  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={2} strokeLinecap="round" aria-hidden="true">
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M15 4v16" />
    </svg>
  );
}

// Dashboard grid, matching the icon the other agent pages use for /home.
// The old roof-shaped HomeSvg read as "back to landing" rather than "back to
// the QuestAI dashboard".
function DashboardSvg() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="14" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
    </svg>
  );
}

function TrashSvg() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 6h18" />
      <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
      <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
      <line x1="10" y1="11" x2="10" y2="17" />
      <line x1="14" y1="11" x2="14" y2="17" />
    </svg>
  );
}

function CloseSvg() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
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
  const [stale, setStale] = useState(false); // running but no fresh progress
  const [confirm, setConfirm] = useState(null); // { proposed }
  const [deleteTarget, setDeleteTarget] = useState(null); // session to delete
  const [inspector, setInspector] = useState(null); // evidence item
  const [openFindings, setOpenFindings] = useState({});
  const [panelOpen, setPanelOpen] = useState(false);
  const [notice, setNotice] = useState("");

  const pollRef = useRef(null);
  const autoRunRef = useRef(false);
  const routerPrefill = useRouterPrefill("research");
  const elapsedRef = useRef(null);
  const startedRef = useRef(null);
  const staleRef = useRef(false);
  const inputRef = useRef(null);

  const handleTipClick = (q) => {
    setInput(q);
    if (inputRef.current) {
      inputRef.current.focus();
    }
  };

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

  const pollUntilDone = (id, initialDoc = null) => {
    stopPoll();
    setRunning(true);
    staleRef.current = false;

    if (initialDoc) {
      startedRef.current = initialDoc.started_at || initialDoc.created_at || null;
      setElapsed(runSeconds(initialDoc));
      setStale(false);
    } else {
      startedRef.current = null;
      setElapsed(0);
      setStale(false);
    }

    elapsedRef.current = setInterval(
      () => setElapsed(runSeconds({ started_at: startedRef.current })),
      1000
    );

    let tries = 0;
    let errs = 0;
    pollRef.current = setInterval(async () => {
      tries += 1;
      try {
        const d = await researchApi.getSession(id);
        errs = 0;
        startedRef.current = d.started_at || d.created_at || startedRef.current;
        setElapsed(runSeconds(d));
        setDoc(d);
        if (d.status !== "running") {
          stopPoll();
          setRunning(false);
          setStale(false);
          staleRef.current = false;
          loadSessions();
        } else if (isFresh(d)) {
          // Server is alive and writing progress — reset stale + tries
          tries = 0;
          if (staleRef.current) {
            staleRef.current = false;
            setStale(false);
          }
        } else {
          // Only mark stale if no updates received after 8 consecutive polls (12s+)
          if (tries >= 8 && !staleRef.current) {
            staleRef.current = true;
            setStale(true);
          }
          if (tries >= POLL_MAX) {
            stopPoll();
            setRunning(false);
            loadSessions();
          }
        }
      } catch (e) {
        if (e.code === "unauthorized") {
          stopPoll();
          setRunning(false);
          navigate("/login", { replace: true });
        } else if (++errs >= 10) {
          stopPoll();
          setRunning(false);
          setStale(false);
          setNotice("Lost connection to the server. Restart the backend and refresh.");
        }
      }
    }, POLL_MS);
  };

  const submit = async (rawQuery, opts = {}) => {
    const query = (rawQuery || "").trim();
    if (!query || running) return;

    // Instant UI feedback: clear input and lock running state immediately
    setInput("");
    setRunning(true);
    setNotice("");
    setInspector(null);
    setConfirm(null);

    // Optimistically update document conversation if active session exists
    if (doc) {
      setDoc((prev) => {
        if (!prev) return prev;
        const conv = [...(prev.conversation || [])];
        conv.push({ user: query, assistant: "" });
        return { ...prev, conversation: conv, status: "running" };
      });
    }

    const targetId = opts.force_new ? undefined : sessionId;
    try {
      const res = await researchApi.run({
        query,
        session_id: targetId,
        force_new: opts.force_new,
        force_continue: opts.force_continue,
      });
      if (res.needs_confirm) {
        setRunning(false);
        setConfirm({ proposed: res.proposed_new_goal || query });
        return;
      }
      if (!targetId || res.session_id !== targetId) {
        navigate(`/research/${res.session_id}`, { replace: !targetId });
      }
      setPanelOpen(false);
      pollUntilDone(res.session_id);
    } catch (e) {
      setRunning(false);
      if (e.code === "unauthorized") {
        navigate("/login", { replace: true });
        return;
      }
      if (e.code === 409 && e.detail?.session_id) {
        pollUntilDone(e.detail.session_id); // already running — attach to it
        return;
      }
      setInput(query); // restore query so user doesn't lose text
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
      setStale(false);
      stopPoll();
      return;
    }
    let alive = true;
    researchApi
      .getSession(sessionId)
      .then((d) => {
        if (!alive) return;
        setDoc(d);
        if (d.status === "running") {
          // Pass the doc so pollUntilDone can detect stale immediately
          pollUntilDone(sessionId, d);
        } else {
          setRunning(false);
          setStale(false);
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

  // ?q= from the dashboard hands the question over. When the router had every
  // field it needed, autoRun starts the run itself — the query is the only
  // required field, so there is nothing to ask. Otherwise it only pre-fills, the
  // same path the empty-state tip cards use. The param is stripped either way so
  // a refresh can't re-fire over the user's edits.
  useEffect(() => {
    const q = searchParams.get("q");
    if (!q || autoRunRef.current || sessionId) return;
    autoRunRef.current = true;
    setSearchParams({}, { replace: true });
    // The router's extracted query is cleaner than the raw sentence.
    const query = routerPrefill?.fields?.query || q;
    if (routerPrefill?.autoRun) submit(query);
    else handleTipClick(query);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, sessionId]);

  const newChat = () => {
    stopPoll();
    startedRef.current = null;
    setRunning(false);
    setStale(false);
    staleRef.current = false;
    setDoc(null);
    setInput("");
    setConfirm(null);
    setInspector(null);
    setNotice("");
    setPanelOpen(false);
    navigate("/research");
  };

  const deleteSession = async (id) => {
    try {
      await researchApi.remove(id);
    } catch {
      setNotice("Could not delete this session.");
      return;
    }
    if (id === sessionId) {
      stopPoll();
      startedRef.current = null;
      setRunning(false);
      setDoc(null);
      navigate("/research");
    }
    loadSessions();
  };

  const cancelRun = async () => {
    if (!sessionId) return;
    stopPoll();
    setRunning(false);
    setStale(false);
    setDoc((prev) => (prev ? { ...prev, status: "cancelled" } : null));
    try {
      await researchApi.cancel(sessionId);
    } catch {
      /* ignore error */
    }
    const d = await researchApi.getSession(sessionId).catch(() => null);
    if (d) setDoc(d);
    loadSessions();
  };

  const report = doc?.report || null;
  const refs = buildRefNumbers(report, doc?.evidence);
  const openRef = (ref) => setInspector((doc.evidence || []).find((e) => e.id === ref) || null);
  const quality = report?.validation_notes?.overall_quality;

  const toggleFinding = (i) => setOpenFindings((m) => ({ ...m, [i]: m[i] === false }));

  return (
    <div className="rs">
      {/* report workspace */}
      <main className="rs-main">
        <header className="rs-top">
          <button className="rs-top-btn" onClick={() => setPanelOpen(true)} aria-label="Open sessions">
            <PanelSvg />
          </button>
          <div className="rs-title">
            <h1>{doc?.query || "Research"}</h1>
            {doc && (
              <span className="rs-meta">
                {statusDot(doc.status)} {doc.status}
                {doc.last_route && doc.last_route !== "full" && (
                  <span className="rs-quality" style={{ opacity: 0.85 }}>
                    {" "}· {doc.last_route} mode
                  </span>
                )}
                {quality && quality !== "unknown" && (
                  <span className="rs-quality"> · {quality} ✓</span>
                )}
                {doc.status !== "running" && (
                  <span className="rs-meta-time"> · {timeAgo(doc.updated_at)}</span>
                )}
              </span>
            )}
          </div>
          <button className="rs-top-btn" onClick={newChat} aria-label="New chat">
            <NewChatSvg />
          </button>
        </header>

        {notice && (
          <div className="rs-alert rs-alert-warn" role="alert">
            <span className="rs-alert-icon">⚠</span>
            <span className="rs-alert-body">{notice}</span>
          </div>
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
                  <button key={q} type="button" className="rs-empty-card" onClick={() => handleTipClick(q)}>
                    “{q}”
                  </button>
                )
              )}
            </div>
          </section>
        ) : (
          doc && (
            <article className="rs-doc">
              {/* Q1 User Prompt (Right Aligned) */}
              <div className="rs-user-prompt-wrap">
                <div className="rs-user-prompt">
                  <span className="rs-user-q-num">Q1</span>
                  <span className="rs-user-q-text">{doc.conversation?.[0]?.user || doc.query}</span>
                </div>
              </div>

              {/* Primary Research Report Canvas */}
              {report?.executive_summary && (
                <section>
                  <p className="rs-sect">Executive summary</p>
                  <p className="rs-summary">{renderRich(report.executive_summary, refs, openRef)}</p>
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
                              {renderRich(f.explanation, refs, openRef)}{" "}
                              {(f.evidence_refs || [])
                                .filter((r) => !(f.explanation || "").includes(r) && refs.has(r))
                                .map((r) => (
                                  <button
                                    key={r}
                                    className="rs-ref"
                                    title="View evidence"
                                    onClick={() => openRef(r)}
                                  >
                                    [{refs.num(r)}]
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
                  <p>{renderRich(report.comparison, refs, openRef)}</p>
                </section>
              )}
              {report?.recent_developments && (
                <section>
                  <p className="rs-sect">Recent developments</p>
                  <p>{renderRich(report.recent_developments, refs, openRef)}</p>
                </section>
              )}
              {report?.limitations && (
                <section>
                  <p className="rs-sect">Limitations</p>
                  <p>{renderRich(report.limitations, refs, openRef)}</p>
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

              {/* Follow-up Questions Section */}
              {doc.conversation && doc.conversation.length > 1 && (
                <section className="rs-followups-section">
                  {doc.conversation.slice(1).map((t, i) => (
                    <article key={i} className="rs-followup-turn">
                      {/* Q2, Q3 User Prompt (Right Aligned) */}
                      <div className="rs-user-prompt-wrap">
                        <div className="rs-user-prompt">
                          <span className="rs-user-q-num">Q{i + 2}</span>
                          <span className="rs-user-q-text">{t.user}</span>
                        </div>
                      </div>

                      {/* Assistant Answer (Left Aligned Full Width) */}
                      <div className="rs-followup-body">
                        {t.route && t.route !== "full" && (
                          <span className="rs-route-tag">{t.route} mode</span>
                        )}
                        {t.assistant ? (
                          renderMarkdown(cleanAssistantAnswer(t.assistant), refs, openRef)
                        ) : (
                          <p className="rs-text-muted">Generating answer...</p>
                        )}
                      </div>
                    </article>
                  ))}
                </section>
              )}

              {doc.status === "failed" && (
                <p className="rs-notice">
                  This run failed{doc.error ? `: ${doc.error}` : ". Ask again to retry."}
                </p>
              )}
              {doc.status === "cancelled" && (
                <p className="rs-notice">Run cancelled. Ask again whenever ready.</p>
              )}
            </article>
          )
        )}

        {/* Floating Sticky Progress Pipeline — ALWAYS visible above input bar when running */}
        {(() => {
          const isRunning = running || doc?.status === "running";
          if (!isRunning) return null;

          const stage = doc?.progress?.stage;
          const detail = doc?.progress?.detail;
          const found = STAGES.findIndex((s) => s.key === stage);
          const cur = found < 0 ? 0 : found;

          if (stale) {
            return (
              <div className="rs-floating-progress-wrap">
                <section className="rs-stale rs-pipe-floating" aria-live="polite">
                  <div className="rs-stale-header">
                    <span className="rs-stale-icon">⚠</span>
                    <div>
                      <p className="rs-stale-title">Session appears stuck</p>
                      <p className="rs-stale-sub">
                        The backend task is taking longer than expected or the server was restarted.
                      </p>
                    </div>
                  </div>
                  <div className="rs-stale-stages">
                    {STAGES.map((s, i) => (
                      <span key={s.key} className={`rs-pipe-step${i > cur ? " rs-pipe-todo" : ""}`}>
                        {i < cur ? (
                          <span className="rs-done">✓</span>
                        ) : i === cur ? (
                          <span className="rs-stale-spin" />
                        ) : (
                          <span className="rs-todo-dot" />
                        )}
                        {s.label}
                      </span>
                    ))}
                  </div>
                  <div className="rs-stale-actions">
                    <button className="rs-cancel rs-cancel-danger" onClick={cancelRun}>
                      Cancel run
                    </button>
                    <span className="rs-stale-hint">Polling for backend updates…</span>
                  </div>
                </section>
              </div>
            );
          }

          return (
            <div className="rs-floating-progress-wrap">
              <section className="rs-pipe rs-pipe-floating" aria-live="polite">
                {STAGES.map((s, i) => (
                  <span key={s.key} className={`rs-pipe-step${i > cur ? " rs-pipe-todo" : ""}`}>
                    {i < cur ? (
                      <span className="rs-done">✓</span>
                    ) : i === cur ? (
                      <span className="rs-pulse" />
                    ) : (
                      <span className="rs-todo-dot" />
                    )}
                    {s.label}
                  </span>
                ))}
                <span className="rs-pipe-time">
                  {detail || "In progress…"} · {fmtElapsed(elapsed)}
                </span>
                <button className="rs-cancel" onClick={cancelRun}>
                  ✕ Cancel
                </button>
              </section>
            </div>
          );
        })()}

        <form
          className="rs-ask"
          onSubmit={(e) => {
            e.preventDefault();
            if (input.trim() && !running) {
              submit(input);
            }
          }}
        >
          <input
            ref={inputRef}
            placeholder={running ? "Researching — input locked..." : "Ask a follow-up or start a topic..."}
            value={input}
            disabled={running}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (input.trim() && !running) {
                  submit(input);
                }
              }
            }}
          />
          <button
            type="submit"
            aria-label="Send"
            disabled={running || !input.trim()}
            onClick={(e) => {
              e.preventDefault();
              if (input.trim() && !running) {
                submit(input);
              }
            }}
          >
            <SendIcon />
          </button>
        </form>
      </main>

      {/* thin icon rail — right side, always visible */}
      <aside className="rs-rail" aria-label="Primary">
        <button className="rs-rail-btn rs-rail-new" title="New chat" onClick={newChat}>
          <NewChatSvg />
        </button>
        <button
          className={`rs-rail-btn${panelOpen ? " active" : ""}`}
          title="Sessions"
          onClick={() => setPanelOpen((p) => !p)}
        >
          <PanelSvg />
        </button>
        <div className="rs-rail-spacer" />
        <Link to="/home" className="rs-rail-btn" title="Dashboard" aria-label="Dashboard">
          <DashboardSvg />
        </Link>
      </aside>

      {/* sessions — slide-over panel from right, all screens */}
      <aside className={`rs-sessions${panelOpen ? " open" : ""}`} aria-label="Sessions">
        <div className="rs-sess-head">
          <button className="rs-close-btn" onClick={() => setPanelOpen(false)} aria-label="Close sessions" title="Close">
            <CloseSvg />
          </button>
          <span className="rs-sess-actions">
            <Link to="/home" className="rs-rail-btn" title="Dashboard" aria-label="Dashboard">
              <DashboardSvg />
            </Link>
            <button className="rs-rail-btn" title="New chat" onClick={newChat} aria-label="New chat">
              <NewChatSvg />
            </button>
          </span>
        </div>
        <div className="rs-sess-list">
          {sessions.length === 0 && <p className="rs-sess-empty">No sessions yet.</p>}
          {sessions.map((s) => (
            <div key={s.session_id} className={`rs-sess${s.session_id === sessionId ? " active" : ""}`}>
              <button
                className="rs-sess-open"
                onClick={() => {
                  setPanelOpen(false);
                  navigate(`/research/${s.session_id}`);
                }}
              >
                {statusDot(s.status)}
                <span className="rs-sess-q">{s.query}</span>
                <span className="rs-sess-t">{timeAgo(s.updated_at)}</span>
              </button>
              <button
                className="rs-sess-del"
                title="Delete session"
                aria-label="Delete session"
                onClick={(e) => {
                  e.stopPropagation();
                  setDeleteTarget(s);
                }}
              >
                <TrashSvg />
              </button>
            </div>
          ))}
        </div>
      </aside>
      {panelOpen && <div className="rs-scrim" onClick={() => setPanelOpen(false)} />}

      {/* delete session confirmation modal */}
      {deleteTarget && (
        <div className="rs-insp-wrap" style={{ display: "grid", placeItems: "center" }}>
          <div className="rs-insp" style={{ height: "auto", borderRadius: 16, width: "min(400px, 90vw)" }}>
            <div className="rs-insp-head">
              <strong>Delete Session?</strong>
              <button className="rs-close-btn" onClick={() => setDeleteTarget(null)} aria-label="Close">
                <CloseSvg />
              </button>
            </div>
            <p style={{ marginTop: 10, marginBottom: 6, fontSize: 14 }}>
              Are you sure you want to delete this research session?
            </p>
            <p style={{ color: "var(--muted)", fontSize: 13, marginBottom: 18, fontStyle: "italic", wordBreak: "break-word" }}>
              “{deleteTarget.query}”
            </p>
            <div className="rs-confirm-row" style={{ justifyContent: "flex-end" }}>
              <button
                className="rs-cancel"
                style={{ padding: "8px 16px", fontSize: 13 }}
                onClick={() => setDeleteTarget(null)}
              >
                Cancel
              </button>
              <button
                className="rs-cancel rs-cancel-danger"
                style={{ padding: "8px 16px", fontSize: 13 }}
                onClick={() => {
                  const id = deleteTarget.session_id;
                  setDeleteTarget(null);
                  deleteSession(id);
                }}
              >
                Delete session
              </button>
            </div>
          </div>
        </div>
      )}

      {/* evidence inspector overlay */}
      {inspector && (
        <div className="rs-insp-wrap">
          <div className="rs-insp">
            <div className="rs-insp-head">
              <strong>{inspector.id}</strong>
              <button className="rs-close-btn" onClick={() => setInspector(null)} aria-label="Close">
                <CloseSvg />
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
