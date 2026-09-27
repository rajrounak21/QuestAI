import { useState, useRef } from 'react'
import { ArrowRight, Sparkles, Upload, X, FileText, Briefcase, MapPin, Plus } from 'lucide-react'

const suggestions = [
  'AI Engineer Internships in India remote',
  'Python Backend internships in Bangalore',
  'Barista in Austin, Texas',
  'Data Science internships in Delhi remote',
]

export default function JobSearch({ onSearch, loading }) {
  const [query, setQuery] = useState('')
  const [resumeFile, setResumeFile] = useState(null)
  const [roles, setRoles] = useState([])
  const [roleInput, setRoleInput] = useState('')
  const [locations, setLocations] = useState([])
  const [locInput, setLocInput] = useState('')
  const [workMode, setWorkMode] = useState('')
  const fileRef = useRef(null)

  const addRole = () => {
    const v = roleInput.trim()
    if (!v) return
    if (roles.length >= 3) return
    const parts = v.split(',').map(s => s.trim()).filter(Boolean)
    const next = [...roles]
    for (const p of parts) {
      if (next.length >= 3) break
      if (next.map(x => x.toLowerCase()).includes(p.toLowerCase())) continue
      next.push(p)
    }
    setRoles(next)
    setRoleInput('')
  }
  const addLoc = () => {
    const v = locInput.trim()
    if (!v) return
    if (locations.length >= 4) return
    const parts = v.split(',').map(s => s.trim()).filter(Boolean)
    const next = [...locations]
    for (const p of parts) {
      if (next.length >= 4) break
      if (next.map(x => x.toLowerCase()).includes(p.toLowerCase())) continue
      next.push(p)
    }
    setLocations(next)
    setLocInput('')
  }

  const buildQuery = () => {
    // Structured fields take priority — builds simple query that hits fast-path (no LLM)
    const roleStr = roles.join(', ')
    const locStr = locations.join(', ')
    if (roleStr && locStr) {
      const base = `${roleStr} in ${locStr}`
      return workMode ? `${base} ${workMode}` : base
    }
    if (roleStr) return workMode ? `${roleStr} ${workMode}` : roleStr
    if (locStr) {
      if (query.trim()) return `${query.trim()} in ${locStr}${workMode ? ' ' + workMode : ''}`
      return workMode ? `${locStr} ${workMode}` : `jobs in ${locStr}`
    }
    if (query.trim()) return workMode && !query.toLowerCase().includes(workMode) ? `${query.trim()} ${workMode}` : query.trim()
    return ''
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    const q = buildQuery()
    if (!q && !resumeFile) return
    const locs = locations.join(', ') || undefined
    onSearch({ query: q, resumeFile, locations: locs })
  }

  const handleSuggestion = (s) => {
    // suggestions are full queries — clear structured fields, use query
    setQuery(s)
    setRoles([])
    setLocations([])
    onSearch({ query: s, resumeFile, locations: undefined })
  }

  const handleFile = (e) => {
    const f = e.target.files?.[0]
    if (f) {
      if (f.type !== 'application/pdf' && !f.name.toLowerCase().endsWith('.pdf')) {
        alert('Please upload a PDF resume')
        return
      }
      if (f.size > 5 * 1024 * 1024) {
        alert('Resume too large (max 5MB)')
        return
      }
      setResumeFile(f)
    }
  }

  const clearFile = () => {
    setResumeFile(null)
    if (fileRef.current) fileRef.current.value = ''
  }

  return (
    <div className="search-hero">
      <form className="job-search" onSubmit={handleSubmit}>
        {/* free-text query kept hidden for suggestion handling only */}
        <input type="hidden" value={query} readOnly />

        <div className="structured-row">
          <div className="struct-field">
            <label className="struct-label"><Briefcase size={12} /> Job role <span className="muted">(up to 3)</span></label>
            <div className="chip-input-wrap">
              <input
                value={roleInput}
                onChange={(e) => setRoleInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addRole() } }}
                placeholder="Add role — e.g. Python Developer"
                disabled={loading || roles.length >= 3}
              />
              <button type="button" className="add-btn" onClick={addRole} disabled={loading || !roleInput.trim()}><Plus size={14} /></button>
            </div>
            {roles.length > 0 && (
              <div className="loc-chips" style={{ marginTop: '.45rem' }}>
                {roles.map(r => (
                  <span key={r} className="role-chip">{r} <button type="button" onClick={() => setRoles(roles.filter(x => x !== r))}><X size={12} /></button></span>
                ))}
              </div>
            )}
          </div>

          <div className="struct-field">
            <label className="struct-label"><MapPin size={12} /> Preferred locations <span className="muted">(up to 4)</span></label>
            <div className="chip-input-wrap">
              <input
                value={locInput}
                onChange={(e) => setLocInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addLoc() } }}
                placeholder="Add location — e.g. Patna, Delhi, Remote"
                disabled={loading || locations.length >= 4}
              />
              <button type="button" className="add-btn" onClick={addLoc} disabled={loading || !locInput.trim()}><Plus size={14} /></button>
            </div>
            {locations.length > 0 && (
              <div className="loc-chips" style={{ marginTop: '.45rem' }}>
                {locations.map(l => (
                  <span key={l} className="loc-chip">{l} <button type="button" onClick={() => setLocations(locations.filter(x => x !== l))}><X size={12} /></button></span>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="workmode-row" style={{ marginTop: '.6rem' }}>
          <span className="wm-label">Work mode:</span>
          {['remote', 'hybrid', 'onsite'].map(m => (
            <button key={m} type="button" className={`wm-chip ${workMode === m ? 'active' : ''}`} onClick={() => setWorkMode(workMode === m ? '' : m)} disabled={loading}>{m}</button>
          ))}
          {workMode && <button type="button" className="wm-chip" onClick={() => setWorkMode('')}>clear</button>}
        </div>

        <div className="resume-row">
          <input ref={fileRef} type="file" accept=".pdf,application/pdf" onChange={handleFile} hidden disabled={loading} />
          {!resumeFile ? (
            <button type="button" className="upload-btn" onClick={() => fileRef.current?.click()} disabled={loading}>
              <Upload size={14} /> Upload Resume (PDF, optional)
            </button>
          ) : (
            <div className="file-chip">
              <FileText size={14} /> {resumeFile.name} <span className="file-size">({(resumeFile.size / 1024).toFixed(0)} KB)</span>
              <button type="button" className="chip-x" onClick={clearFile}><X size={14} /></button>
            </div>
          )}
          <span className="resume-hint">Resume adds skills — roles/locations above skip LLM parsing</span>
        </div>

        <div className="search-suggestions">
          <span className="sugg-label"><Sparkles size={12} /> Try:</span>
          {suggestions.map(s => (
            <button key={s} type="button" className="sugg-chip" onClick={() => handleSuggestion(s)} disabled={loading}>{s}</button>
          ))}
        </div>
        <button type="submit" disabled={loading || (!buildQuery() && !resumeFile)} className="search-btn" style={{ width: '100%', marginTop: '.85rem', justifyContent: 'center' }}>
          {loading ? <span className="btn-loading"><span className="spinner-small" /> Searching</span> : <>Search <ArrowRight size={16} /></>}
        </button>
        <p className="search-hint"><span className="dot-pulse" /> Live from Google Jobs · 2-3 queries · deduplicated & fresh-first · Structured role/location avoids LLM</p>
      </form>
    </div>
  )
}
