import { useCallback, useEffect, useRef, useState } from "react";
import {
  X, FileText, Upload, Trash2, RefreshCw, GraduationCap,
  Briefcase, FolderGit2, ChevronDown, User,
} from "lucide-react";
import { getProfile, fetchResumePdf, deleteProfile, uploadResume } from "./api";
import { timeAgo } from "../src/shared/api";
import ConfirmModal from "./ConfirmModal";

// Profile panel: preview the stored resume PDF, replace it, or delete it.
// Replace re-runs the same LLM extraction as onboarding and fully overwrites the
// stored profile + PDF — nothing is appended.
export default function ProfilePanel({ onClose, onChanged }) {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [hasPdf, setHasPdf] = useState(false);
  const [pdfUrl, setPdfUrl] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [showData, setShowData] = useState(false);
  const [pdfReload, setPdfReload] = useState(0);
  const inputRef = useRef(null);

  // Object URL for the <iframe>. Revoked on change/unmount to avoid leaking blobs.
  useEffect(() => {
    let url = null;
    let cancelled = false;
    (async () => {
      try {
        const blob = await fetchResumePdf();
        if (cancelled || !blob) return;
        url = URL.createObjectURL(blob);
        setPdfUrl(url);
      } catch {
        // No preview available — the panel shows the upload fallback instead.
      }
    })();
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [hasPdf, pdfReload]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await getProfile();
      setProfile(d.profile || null);
      setHasPdf(!!d.has_resume_pdf);
    } catch (e) {
      setError(e.message || "Could not load your profile.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleFile = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (!f.name.toLowerCase().endsWith(".pdf")) {
      setError("Please upload a PDF resume.");
      return;
    }
    if (f.size > 5 * 1024 * 1024) {
      setError("Resume too large (max 5MB).");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      // Same endpoint as onboarding — replaces profile + PDF wholesale.
      const res = await uploadResume(f);
      setProfile(res.profile || null);
      setHasPdf(true);
      setPdfReload((n) => n + 1); // re-fetch the PDF blob
      if (onChanged) onChanged(res.profile);
    } catch (err) {
      setError(err.message || "Replace failed. Try again.");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const handleDelete = async () => {
    setBusy(true);
    try {
      await deleteProfile();
      setConfirmDelete(false);
      setProfile(null);
      setHasPdf(false);
      setPdfUrl(null);
      if (onChanged) onChanged(null);
      onClose();
    } catch (err) {
      setError(err.message || "Delete failed.");
    } finally {
      setBusy(false);
    }
  };

  const skills = profile?.skills || [];
  const education = profile?.education || [];
  const experience = profile?.experience || [];
  const projects = profile?.projects || [];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card profile-panel" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose} aria-label="Close"><X size={16} /></button>

        <h3 className="modal-title"><User size={16} /> Your resume</h3>

        {loading ? (
          <div className="resume-preview resume-preview-loading">Loading…</div>
        ) : !profile ? (
          <div className="empty-state">No resume saved yet.</div>
        ) : (
          <>
            <div className="profile-file-row">
              <FileText size={15} />
              <div className="profile-file-meta">
                <strong>{profile.resume_filename || "resume.pdf"}</strong>
                <span>{profile.updated_at ? `updated ${timeAgo(profile.updated_at)}` : ""}</span>
              </div>
              <button className="job-btn" onClick={() => inputRef.current?.click()} disabled={busy}>
                {busy ? <><span className="spinner-small" /> Working…</> : <><RefreshCw size={13} /> Replace</>}
              </button>
              <button className="job-btn ghost" onClick={() => setConfirmDelete(true)} disabled={busy} title="Delete resume">
                <Trash2 size={13} />
              </button>
              <input ref={inputRef} type="file" accept=".pdf,application/pdf" onChange={handleFile} hidden disabled={busy} />
            </div>

            {error && <div className="empty-state error profile-error">{error}</div>}

            {hasPdf && pdfUrl ? (
              <iframe src={pdfUrl} title="Resume preview" className="resume-frame" />
            ) : (
              <div className="resume-preview-empty">
                <Upload size={22} />
                <p>No stored PDF to preview</p>
                <button className="search-btn" onClick={() => inputRef.current?.click()} disabled={busy}>
                  <Upload size={14} /> Upload resume
                </button>
              </div>
            )}

            <button className="profile-data-toggle" onClick={() => setShowData(v => !v)} aria-expanded={showData}>
              <ChevronDown size={14} className={showData ? "flip" : ""} />
              What we extracted
              <span className="muted">
                {skills.length} skills · {education.length} education · {experience.length} experience · {projects.length} projects
              </span>
            </button>

            {showData && (
              <div className="profile-data">
                {skills.length > 0 && (
                  <div className="profile-data-sec">
                    <h4>Skills</h4>
                    <div className="loc-chips">
                      {skills.map((s) => <span key={s} className="profile-chip skill">{s}</span>)}
                    </div>
                  </div>
                )}
                {education.length > 0 && (
                  <div className="profile-data-sec">
                    <h4><GraduationCap size={13} /> Education</h4>
                    {education.map((e, i) => (
                      <p key={i} className="profile-data-row">{[e.degree, e.school, e.year].filter(Boolean).join(" · ")}</p>
                    ))}
                  </div>
                )}
                {experience.length > 0 && (
                  <div className="profile-data-sec">
                    <h4><Briefcase size={13} /> Experience</h4>
                    {experience.map((x, i) => (
                      <p key={i} className="profile-data-row">{[x.title, x.company, x.duration].filter(Boolean).join(" · ")}</p>
                    ))}
                  </div>
                )}
                {projects.length > 0 && (
                  <div className="profile-data-sec">
                    <h4><FolderGit2 size={13} /> Projects</h4>
                    {projects.map((p, i) => (
                      <p key={i} className="profile-data-row">{[p.name, p.stack].filter(Boolean).join(" · ")}</p>
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {confirmDelete && (
        <ConfirmModal
          open
          title="Delete your resume?"
          message="This removes your stored resume and extracted skills. Job searches will need a new upload."
          confirmText="Delete"
          loading={busy}
          onConfirm={handleDelete}
          onCancel={() => setConfirmDelete(false)}
        />
      )}
    </div>
  );
}
