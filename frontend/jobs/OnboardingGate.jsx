import { useEffect, useRef, useState } from "react";
import { Upload, FileText, X, Sparkles, Loader, GraduationCap, Briefcase } from "lucide-react";
import { uploadResume } from "./api";

// The single place a resume is ever uploaded. Two modes:
//   mode="onboarding" — first visit to /jobs. A "Skip for now" is allowed.
//   mode="required"   — the user searched without stored skills (HTTP 409).
//                       No bypass: without a resume every job scores 0%, so the
//                       search cannot proceed.
// Skip is available on first visit only, and disappears while the server reads
// the resume. In "required" mode there is no skip at all.
//
// `reason` only changes the wording, so the same gate can be reused when a job
// alert is being created. Alert creation is also required (no skip): the resume
// is what lets the alert drop senior-only postings, and the backend rejects
// creating an alert without one.
export default function OnboardingGate({ onDone, onSkip, mode = "onboarding", reason = "search" }) {
  const inputRef = useRef(null);
  const timerRef = useRef(null);
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const isAlert = reason === "alert";
  const required = mode === "required" || isAlert;

  const COPY = isAlert
    ? {
        title: "Upload your resume first",
        sub: "Your resume tells us your experience level, so the alert only emails jobs you are actually eligible for.",
        hint: "Your resume is required to create a job alert.",
      }
    : {
        title: "Upload your resume to continue",
        sub: "We match every result against your skills, so we need your resume before searching.",
        hint: "Your resume is required to match jobs against your skills.",
      };
  const copy = COPY;

  // The auto-continue timer must not fire after unmount (user navigated away).
  useEffect(() => () => {
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  const pick = (e) => {
    const f = e.target.files?.[0];
    setError(null);
    if (!f) return;
    if (!f.name.toLowerCase().endsWith(".pdf")) {
      setError("Please upload a PDF resume.");
      return;
    }
    if (f.size > 5 * 1024 * 1024) {
      setError("Resume too large (max 5MB).");
      return;
    }
    setFile(f);
  };

  const submit = async () => {
    if (!file || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await uploadResume(file);
      setResult(res.profile || {});
      // Show what was extracted, then continue automatically.
      timerRef.current = setTimeout(() => onDone(res.profile), 900);
    } catch (e) {
      setError(e.message || "Upload failed. Try again.");
      setBusy(false);
    }
  };

  const skills = result?.skills || [];
  const education = result?.education || [];
  const experience = result?.experience || [];

  return (
    <div className="modal-overlay">
      <div className="modal-card">
        <h3 className="modal-title">
          <Sparkles size={16} />
          {mode === "required" || isAlert ? copy.title : "Match jobs to your skills"}
        </h3>
        <p className="modal-sub">
          {required
            ? copy.sub
            : "Upload your resume once. We pull out your skills so every job you see gets a match score. You won't need to upload it again."}
        </p>

        {result ? (
          <div className="parse-result">
            <div className="parse-ok">
              <Sparkles size={14} /> Saved — {skills.length} skill{skills.length === 1 ? "" : "s"} extracted
            </div>
            {skills.length > 0 && <div className="loc-chips">{skills.slice(0, 10).map(s => <span key={s} className="profile-chip skill">{s}</span>)}</div>}
            {education.length > 0 && (
              <p className="parse-line"><GraduationCap size={12} /> {education.map(e => [e.degree, e.school].filter(Boolean).join(", ")).join(" · ")}</p>
            )}
            {experience.length > 0 && (
              <p className="parse-line"><Briefcase size={12} /> {experience.map(x => x.title).filter(Boolean).join(" · ")}</p>
            )}
          </div>
        ) : (
          <>
        <div className="modal-section">
          <label className="modal-label">
            <FileText size={13} /> Resume (PDF, max 5MB)
          </label>
          {!file ? (
            <button
              type="button"
              className="search-btn"
              style={{ width: "100%", justifyContent: "center" }}
              onClick={() => inputRef.current?.click()}
              disabled={busy}
            >
              <Upload size={14} /> Choose PDF
            </button>
          ) : (
            <div className="loc-chips" style={{ marginTop: ".5rem" }}>
              <span className="loc-chip">
                {file.name}
                <button onClick={() => setFile(null)} disabled={busy} aria-label="Remove file">
                  <X size={12} />
                </button>
              </span>
            </div>
          )}
          <input
            ref={inputRef}
            type="file"
            accept="application/pdf,.pdf"
            onChange={pick}
            style={{ display: "none" }}
          />
        </div>

        {error && (
          <div className="empty-state error" style={{ padding: ".7rem", marginTop: ".6rem" }}>
            {error}
          </div>
        )}

          <div className="modal-actions">
            {/* Hidden while the server is reading the resume, so nothing can be
                clicked mid-request. Onboarding only — the required gate has no
                way out, since searching without skills returns nothing usable. */}
            {!required && !busy && (
              <button className="job-btn ghost" style={{ flex: 1, justifyContent: "center" }} onClick={onSkip}>
                Skip for now
              </button>
            )}
            <button
              className="search-btn"
              style={{ flex: 1, justifyContent: "center" }}
              onClick={submit}
              disabled={!file || busy}
            >
              {busy ? (
                <>
                  <Loader size={14} /> Reading resume…
                </>
              ) : (
                "Save & continue"
              )}
            </button>
          </div>
          <p className="modal-hint modal-hint-center">
            {required
              ? copy.hint
              : busy
                ? "Hang tight — reading your resume."
                : "Skipping means no skill scores — you can upload later."}
          </p>
          </>
        )}
      </div>
    </div>
  );
}
