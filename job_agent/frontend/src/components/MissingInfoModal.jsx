import { useState, useEffect } from 'react'
import { X, MapPin, Briefcase, FileText } from 'lucide-react'

export default function MissingInfoModal({ question, profile, resumeName, onSubmit, onClose, loading }) {
  const isRoleMissing = !profile?.target_roles?.length
  const isLocMissing = !profile?.locations?.length

  const [roles, setRoles] = useState([])
  const [roleInput, setRoleInput] = useState('')
  const [locations, setLocations] = useState([])
  const [locInput, setLocInput] = useState('')
  const [workMode, setWorkMode] = useState(profile?.work_mode?.[0] || '')

  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [])

  const addRole = () => {
    const v = roleInput.trim()
    if (!v) return
    if (roles.length >= 3) return
    // allow comma separated
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

  const canSubmit = () => {
    if (isRoleMissing && roles.length === 0) return false
    if (isLocMissing && locations.length === 0) return false
    return true
  }

  const handleSubmit = () => {
    const roleStr = roles.join(', ')
    const locStr = locations.join(', ')
    const locWithMode = workMode && locStr ? `${locStr} ${workMode}` : locStr || workMode || ''
    // send both; backend will merge with resume memory
    onSubmit({ query: roleStr || undefined, locations: locWithMode || undefined })
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={e => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}><X size={16} /></button>
        <h3 className="modal-title">Complete your search</h3>
        <p className="modal-sub">{question}</p>

        {resumeName && (
          <div className="modal-resume">
            <FileText size={14} /> {resumeName} <span className="muted">· resume kept in memory</span>
          </div>
        )}

        {(isRoleMissing || roles.length > 0) && (
          <div className="modal-section">
            <label className="modal-label"><Briefcase size={13} /> Job role {isRoleMissing ? '*' : ''} <span className="muted">(up to 3 — comma or Enter)</span></label>
            <div className="chip-input-wrap">
              <input
                value={roleInput}
                onChange={e => setRoleInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addRole() } }}
                placeholder="e.g. Python Developer, AI Engineer"
                disabled={loading}
              />
              <button type="button" className="add-btn" onClick={addRole} disabled={loading || !roleInput.trim()}>+</button>
            </div>
            {roles.length > 0 && (
              <div className="loc-chips" style={{ marginTop: '.6rem' }}>
                {roles.map(r => (
                  <span key={r} className="role-chip">{r} <button onClick={() => setRoles(roles.filter(x => x !== r))}><X size={12} /></button></span>
                ))}
              </div>
            )}
            <p className="modal-hint">Selected roles will search Google Jobs (2-3 queries, deduped)</p>
          </div>
        )}

        {(isLocMissing || locations.length > 0 || true) && (
          <div className="modal-section">
            <label className="modal-label"><MapPin size={13} /> Preferred locations {isLocMissing ? '*' : ''} <span className="muted">(up to 4)</span></label>
            <div className="chip-input-wrap">
              <input
                value={locInput}
                onChange={e => setLocInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addLoc() } }}
                placeholder="Add location (e.g. Patna, Bangalore, Remote)"
                disabled={loading || locations.length >= 4}
              />
              <button type="button" className="add-btn" onClick={addLoc} disabled={loading || !locInput.trim()}>+</button>
            </div>
            {locations.length > 0 && (
              <div className="loc-chips" style={{ marginTop: '.6rem' }}>
                {locations.map(l => (
                  <span key={l} className="loc-chip">{l} <button onClick={() => setLocations(locations.filter(x => x !== l))}><X size={12} /></button></span>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="modal-section">
          <label className="modal-label">Work mode (optional)</label>
          <div className="workmode-row">
            {['remote', 'hybrid', 'onsite'].map(m => (
              <button key={m} type="button" className={`wm-chip ${workMode === m ? 'active' : ''}`} onClick={() => setWorkMode(workMode === m ? '' : m)}>{m}</button>
            ))}
          </div>
        </div>

        <button className="search-btn" style={{ width: '100%', justifyContent: 'center', marginTop: '.8rem' }} onClick={handleSubmit} disabled={loading || !canSubmit()}>
          {loading ? 'Searching…' : 'Search jobs'}
        </button>
        <p className="modal-hint" style={{ textAlign: 'center', marginTop: '.4rem' }}>Simple placeholder — no heavy LLM for this step</p>
      </div>
    </div>
  )
}
