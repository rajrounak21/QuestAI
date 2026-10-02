import { useEffect, useRef, useState } from 'react'
import { ArrowRight, Sparkles, X, Briefcase, MapPin, Plus } from 'lucide-react'
import { parseQuery } from './parseQuery'

const suggestions = [
  'AI Engineer Internships in India remote',
  'Python Backend internships in Bangalore',
  'Barista in Austin, Texas',
  'Data Science internships in Delhi remote',
]

// Roles + location + work mode. There is deliberately NO resume field here:
// the resume is uploaded once through the onboarding / required modal, and the
// backend refuses to search without stored skills (HTTP 409).
//
// prefillRoles / prefillLocations / prefillWorkMode repopulate the form when a
// saved session is restored, so the chips match the jobs on screen.
export default function JobSearch({
  onSearch,
  loading,
  prefillRoles = [],
  prefillLocations = [],
  prefillWorkMode = '',
}) {
  const [roles, setRoles] = useState([])
  const [roleInput, setRoleInput] = useState('')
  const [locations, setLocations] = useState([])
  const [locInput, setLocInput] = useState('')
  const [workMode, setWorkMode] = useState('')
  const inputRef = useRef(null)
  // Re-seed the chips whenever a session restore changes the prefill. Applied
  // unconditionally (not only when non-empty) so tapping a saved search with no
  // stored roles clears the previous ones instead of leaving stale chips.
  useEffect(() => {
    setRoles(prefillRoles);
  }, [prefillRoles]);

  useEffect(() => {
    setLocations(prefillLocations);
  }, [prefillLocations]);

  useEffect(() => {
    setWorkMode(prefillWorkMode);
  }, [prefillWorkMode]);
  const addRole = () => {
    const v = roleInput.trim()
    if (!v || roles.length >= 3) return
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
    if (!v || locations.length >= 4) return
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
    // Structured fields take priority — builds a query the server's
    // deterministic parser handles without any LLM call.
    const roleStr = roles.join(', ')
    const locStr = locations.join(', ')
    if (roleStr && locStr) {
      const base = `${roleStr} in ${locStr}`
      return workMode ? `${base} ${workMode}` : base
    }
    if (roleStr) return workMode ? `${roleStr} ${workMode}` : roleStr
    return locStr
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    const q = buildQuery()
    if (!q) return
    onSearch({ query: q, locations: locations.join(', ') || undefined })
  }

  // "AI Engineer Internships in India remote" -> role, location, work mode.
  // Suggestions fill the form; they never search on their own.
  const handleSuggestion = (s) => {
    const { role, locations: locs, mode } = parseQuery(s)
    setRoles(role ? [role] : [])
    setLocations(locs)
    setWorkMode(mode)
    // Focus the role input so the user can adjust before searching.
    inputRef.current?.focus()
  }

  return (
    <form className="job-search" onSubmit={handleSubmit}>
      <div className="job-search-main">
        <div className="struct-field">
          <label className="struct-label"><Briefcase size={13} /> Job role</label>
          <div className="chip-input-wrap">
            <input
              ref={inputRef}
              value={roleInput}
              onChange={(e) => setRoleInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addRole() } }}
              placeholder="e.g. Python Developer"
              disabled={loading || roles.length >= 3}
            />
            <button type="button" className="add-btn" onClick={addRole} disabled={loading || !roleInput.trim()} aria-label="Add role"><Plus size={15} /></button>
          </div>
          {roles.length > 0 && (
            <div className="loc-chips">
              {roles.map(r => (
                <span key={r} className="role-chip">
                  {r}
                  <button type="button" onClick={() => setRoles(roles.filter(x => x !== r))} aria-label={`Remove ${r}`}><X size={12} /></button>
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="struct-field">
          <label className="struct-label"><MapPin size={13} /> Location</label>
          <div className="chip-input-wrap">
            <input
              value={locInput}
              onChange={(e) => setLocInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addLoc() } }}
              placeholder="e.g. India, Bangalore"
              disabled={loading || locations.length >= 4}
            />
            <button type="button" className="add-btn" onClick={addLoc} disabled={loading || !locInput.trim()} aria-label="Add location"><Plus size={15} /></button>
          </div>
          {locations.length > 0 && (
            <div className="loc-chips">
              {locations.map(l => (
                <span key={l} className="loc-chip">
                  {l}
                  <button type="button" onClick={() => setLocations(locations.filter(x => x !== l))} aria-label={`Remove ${l}`}><X size={12} /></button>
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="struct-field struct-field-work">
          <label className="struct-label">Work mode</label>
          <div className="workmode-row">
            {['remote', 'hybrid', 'onsite'].map(m => (
              <button key={m} type="button" className={`wm-chip ${workMode === m ? 'active' : ''}`} onClick={() => setWorkMode(workMode === m ? '' : m)} disabled={loading}>{m}</button>
            ))}
          </div>
        </div>
      </div>

      <div className="search-suggestions">
        <span className="sugg-label"><Sparkles size={12} /> Try</span>
        {suggestions.map(s => (
          <button key={s} type="button" className="sugg-chip" onClick={() => handleSuggestion(s)} disabled={loading}>
            {s}
            <ArrowRight size={11} className="sugg-go" />
          </button>
        ))}
      </div>

      <button type="submit" disabled={loading || !buildQuery()} className="search-btn search-submit">
        {loading ? <><span className="spinner-small" /> Searching…</> : <>Search jobs <ArrowRight size={16} /></>}
      </button>
      <p className="search-hint search-hint-foot">
        <span className="dot-pulse" /> Live Google Jobs · 2–3 queries · deduped, freshest first
      </p>
    </form>
  )
}
