import { useEffect } from 'react'
import { X, Building2, MapPin, Clock, Banknote, Briefcase, ExternalLink, Award, FileText, Link2 } from 'lucide-react'

const freshnessColor = {
  'Today': '#10b981',
  '1 day ago': '#34d399',
  '3 days ago': '#f59e0b',
  '1 week ago': '#f97316',
  'Older': '#94a3b8',
  'Unknown': '#94a3b8',
}

export default function JobDetails({ job, onClose, onPrepare }) {
  useEffect(() => {
    const onEsc = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onEsc)
    document.body.style.overflow = 'hidden'
    return () => { window.removeEventListener('keydown', onEsc); document.body.style.overflow = '' }
  }, [onClose])

  if (!job) return null
  const bucket = job.freshness_bucket || 'Unknown'

  return (
    <div className="job-details-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-label={`Job details for ${job.title}`}>
      <div className="job-details-modal" onClick={(e) => e.stopPropagation()}>
        <button className="details-close" onClick={onClose} aria-label="Close"><X size={18} /></button>

        {job.thumbnail && (
          <div className="details-thumb">
            <img src={job.thumbnail} alt="" loading="lazy" onError={(e) => e.target.style.display = 'none'} />
          </div>
        )}

        <div className="details-content">
          <div className="details-header">
            <h2 className="details-title">{job.title}</h2>
            <span className="freshness-badge" style={{ background: freshnessColor[bucket] || '#94a3b8' }}>{job.posted_label || bucket}</span>
          </div>
          <p className="details-company"><Building2 size={14} /> {job.company} {job.source ? <span className="via">· {job.source}</span> : null}</p>
          <p className="details-location"><MapPin size={14} /> {job.location || 'Location not specified'} {job.work_mode ? ` · ${job.work_mode}` : ''}</p>

          <div className="details-chips">
            {job.employment_type && <span className="meta-chip"><Briefcase size={12} /> {job.employment_type}</span>}
            {job.salary && <span className="meta-chip salary"><Banknote size={12} /> {job.salary}</span>}
            {job.posted_at && <span className="meta-chip"><Clock size={12} /> {job.posted_at}</span>}
          </div>

          {job.total_user_skills > 0 && (
            <div className="details-section match-section">
              <h4>Your Skills — Resume skill overlap</h4>
              <p className="match-pct-large"><span className={`match-pct ${job.match_percentage >= 60 ? 'high' : job.match_percentage >= 30 ? 'mid' : 'low'}`}>{job.match_percentage}%</span> <span className="muted">{job.matched_count}/{job.total_user_skills} resume skills found</span></p>
              <div className="match-progress"><div className="match-fill" style={{ width: `${job.match_percentage}%` }} /></div>
              {job.matched_skills?.length > 0 && (
                <div style={{ marginTop: '.6rem' }}>
                  <strong style={{ fontSize: '.82rem' }}>Matched ✓</strong>
                  <div className="match-chips" style={{ marginTop: '.35rem' }}>{job.matched_skills.map(s => <span key={s} className="match-chip ok">✓ {s}</span>)}</div>
                </div>
              )}
              {job.missing_skills?.length > 0 && (
                <div style={{ marginTop: '.6rem' }}>
                  <strong style={{ fontSize: '.82rem' }}>Not found in description ○</strong>
                  <div className="match-chips" style={{ marginTop: '.35rem' }}>{job.missing_skills.map(s => <span key={s} className="match-chip miss">○ {s}</span>)}</div>
                  <p className="muted" style={{ fontSize: '.72rem', marginTop: '.4rem' }}>“Not found” doesn’t mean you lack it — only that the description didn’t mention it.</p>
                </div>
              )}
            </div>
          )}

          {job.description && (
            <div className="details-section">
              <h4><FileText size={14} /> Description</h4>
              <p className="details-desc">{job.description}</p>
            </div>
          )}

          {job.job_highlights && job.job_highlights.length > 0 && (
            <div className="details-section">
              <h4><Award size={14} /> Highlights</h4>
              {job.job_highlights.map((h, i) => (
                <div key={i} className="highlight-block">
                  <strong>{h.title}</strong>
                  <ul>{(h.items || []).map((it, j) => <li key={j}>{it}</li>)}</ul>
                </div>
              ))}
            </div>
          )}

          {job.extensions && job.extensions.length > 0 && (
            <div className="details-section">
              <h4>Tags</h4>
              <div className="details-ext">{job.extensions.map((e, i) => <span key={i} className="ext-chip">{e}</span>)}</div>
            </div>
          )}

          {job.detected_extensions && Object.keys(job.detected_extensions).length > 0 && (
            <div className="details-section muted">
              <h4>Detected</h4>
              <div className="detected-grid">
                {Object.entries(job.detected_extensions).map(([k, v]) => (
                  <span key={k} className="detected-item"><strong>{k}:</strong> {String(v)}</span>
                ))}
              </div>
            </div>
          )}

          {job.raw_source?.job_url || job.job_url ? (
            <div className="details-section">
              <h4><Link2 size={14} /> Source</h4>
              <p className="evidence-text">Via {job.source || 'Google Jobs'} · <a href={job.job_url || job.raw_source?.job_url} target="_blank" rel="noopener noreferrer" className="evidence-link">Open original listing</a></p>
              {job.raw_source?.search_url && <p className="evidence-sub">{job.raw_source.search_url.slice(0, 90)}…</p>}
            </div>
          ) : null}

          <div className="details-actions">
            {job.job_url && <a href={job.job_url} target="_blank" rel="noopener noreferrer" className="job-btn primary">View Job <ExternalLink size={14} /></a>}
            <button className="job-btn ghost" onClick={() => onPrepare && onPrepare(job)}>Prepare Application</button>
            {job.apply_url && <a href={job.apply_url} target="_blank" rel="noopener noreferrer" className="job-btn ghost">Apply on {job.apply_url.includes('linkedin') ? 'LinkedIn' : job.apply_url.includes('indeed') ? 'Indeed' : 'Source'} <ExternalLink size={14} /></a>}
          </div>
        </div>
      </div>
    </div>
  )
}
