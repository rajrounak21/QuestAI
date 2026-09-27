import { MapPin, Clock, Building2, Banknote, Briefcase } from 'lucide-react'

const freshnessColor = {
  'Today': '#10b981',
  '1 day ago': '#34d399',
  '3 days ago': '#f59e0b',
  '1 week ago': '#f97316',
  'Older': '#94a3b8',
  'Unknown': '#94a3b8',
  '1 week ago': '#f97316',
}

export default function JobCard({ job, onSelect, onPrepare }) {
  const bucket = job.freshness_bucket || 'Unknown'
  const showBadge = bucket !== 'Unknown' && bucket !== 'Older'
  const handleClick = () => onSelect && onSelect(job)
  const handleKey = (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleClick() } }

  return (
    <div
      className="job-card"
      onClick={handleClick}
      onKeyDown={handleKey}
      role="button"
      tabIndex={0}
      aria-label={`View details for ${job.title} at ${job.company}`}
    >
      <div className="job-card-top">
        <div className="job-title-row">
          <h3 className="job-title" title={job.title}>{job.title}</h3>
          {showBadge && <span className="freshness-badge" style={{ background: freshnessColor[bucket] }}>{job.posted_label || bucket}</span>}
        </div>
        <p className="job-company"><Building2 size={13} /> <span className="company-name">{job.company}</span> {job.source ? <span className="via">· {job.source}</span> : null}</p>
        <p className="job-location"><MapPin size={13} /> {job.location || 'Location not specified'} {job.work_mode ? <span className="via">· {job.work_mode}</span> : null}</p>
        <div className="job-meta-row">
          {job.employment_type && <span className="meta-chip"><Briefcase size={12} /> {job.employment_type}</span>}
          {job.salary && <span className="meta-chip salary"><Banknote size={12} /> {job.salary}</span>}
          {job.posted_at && <span className="meta-chip time"><Clock size={11} /> {job.posted_at}</span>}
        </div>
        {job.description && (
          <p className="job-desc clamp-3">{job.description}</p>
        )}
        {job.extensions?.length > 0 && (
          <div className="job-ext">
            {job.extensions.slice(0, 2).map((e, i) => <span key={i} className="ext-chip">{e}</span>)}
            {job.extensions.length > 2 && <span className="ext-chip more">+{job.extensions.length - 2}</span>}
          </div>
        )}
        {job.total_user_skills > 0 && (
          <div className="match-bar">
            <div className="match-header">
              <span className="match-label">Skill Match</span>
              <span className={`match-pct ${job.match_percentage >= 60 ? 'high' : job.match_percentage >= 30 ? 'mid' : 'low'}`}>{job.match_percentage}%</span>
              <span className="match-count">{job.matched_count}/{job.total_user_skills} resume skills found</span>
            </div>
            <div className="match-progress"><div className="match-fill" style={{ width: `${job.match_percentage}%` }} /></div>
            {job.matched_skills?.length > 0 && (
              <div className="match-chips">
                {job.matched_skills.slice(0, 4).map(s => <span key={s} className="match-chip ok">✓ {s}</span>)}
                {job.matched_skills.length > 4 && <span className="match-chip more">+{job.matched_skills.length - 4}</span>}
              </div>
            )}
          </div>
        )}
      </div>
      <div className="job-actions" onClick={(e) => e.stopPropagation()}>
        {job.job_url ? <a href={job.job_url} target="_blank" rel="noopener noreferrer" className="job-btn primary" onClick={(e) => e.stopPropagation()}>View Job</a> : <span className="job-btn disabled">No link</span>}
        {job.apply_url && job.apply_url !== job.job_url ? (
          <a href={job.apply_url} target="_blank" rel="noopener noreferrer" className="job-btn apply" onClick={(e) => e.stopPropagation()}>Apply</a>
        ) : null}
        <button className="job-btn ghost prepare" onClick={(e) => { e.stopPropagation(); onPrepare && onPrepare(job); }}>Prepare</button>
      </div>
    </div>
  )
}
