import { useState } from 'react'
import { MapPin, Plus, X, Briefcase } from 'lucide-react'

export default function FollowUpLocations({ question, onSubmit, loading }) {
  const isRole = question && question.toLowerCase().includes('what role')
  const isLocation = question && (question.toLowerCase().includes('where would you like to work') || question.toLowerCase().includes('location'))

  const [role, setRole] = useState('')
  const [locations, setLocations] = useState([])
  const [input, setInput] = useState('')
  const [workMode, setWorkMode] = useState('')

  const add = () => {
    const v = input.trim()
    if (!v) return
    if (locations.length >= 4) return
    if (locations.map(l => l.toLowerCase()).includes(v.toLowerCase())) return
    setLocations([...locations, v])
    setInput('')
  }
  const remove = (v) => setLocations(locations.filter(l => l !== v))

  const submit = () => {
    if (isRole) {
      if (!role.trim()) return
      onSubmit({ query: role.trim(), locations: locations.join(', ') ? `${locations.join(', ')}${workMode ? ' ' + workMode : ''}` : (workMode || '') })
    } else {
      const locStr = locations.join(', ')
      const locWithMode = workMode ? `${locStr} ${workMode}`.trim() : locStr
      onSubmit({ locations: locWithMode })
    }
  }

  // Role follow-up: show role input + optional locations
  if (isRole) {
    return (
      <div className="followup-card">
        <p className="followup-question">{question}</p>
        <div className="chip-input-wrap" style={{ marginBottom: '.7rem', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '.5rem .6rem', display: 'flex', gap: '.4rem', alignItems: 'center' }}>
          <Briefcase size={14} color="#64748b" />
          <input
            value={role}
            onChange={(e) => setRole(e.target.value)}
            placeholder="e.g. Python Developer, AI Engineer Intern"
            disabled={loading}
            style={{ flex: 1, border: 'none', outline: 'none', fontSize: '.9rem' }}
          />
        </div>
        <p className="followup-hint" style={{ marginBottom: '.6rem' }}>Add preferred locations (optional, up to 4):</p>
        <div className="chip-input-wrap">
          <MapPin size={14} color="#64748b" />
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add() } }}
            placeholder="Add location (e.g. Bangalore, India, Remote)"
            disabled={loading || locations.length >= 4}
            style={{ flex: 1, border: 'none', outline: 'none', fontSize: '.9rem' }}
          />
          <button type="button" onClick={add} disabled={loading || !input.trim()} className="add-btn"><Plus size={14} /></button>
        </div>
        {locations.length > 0 && (
          <div className="loc-chips" style={{ marginTop: '.7rem', display: 'flex', gap: '.4rem', flexWrap: 'wrap' }}>
            {locations.map(l => (
              <span key={l} className="loc-chip">{l} <button onClick={() => remove(l)}><X size={12} /></button></span>
            ))}
          </div>
        )}
        <div className="workmode-row" style={{ marginTop: '.8rem', display: 'flex', gap: '.4rem', alignItems: 'center' }}>
          <span className="wm-label">Work mode:</span>
          {['remote', 'hybrid', 'onsite'].map(m => (
            <button key={m} type="button" className={`wm-chip ${workMode === m ? 'active' : ''}`} onClick={() => setWorkMode(workMode === m ? '' : m)}>{m}</button>
          ))}
        </div>
        <button className="search-btn followup-submit" onClick={submit} disabled={loading || !role.trim()} style={{ marginTop: '.9rem', width: '100%', justifyContent: 'center' }}>Search jobs</button>
      </div>
    )
  }

  // Default: location follow-up
  return (
    <div className="followup-card">
      <p className="followup-question">{question}</p>
      <div className="followup-input-row">
        <div className="chip-input-wrap">
          <MapPin size={14} color="#64748b" />
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add() } }}
            placeholder="Add location (e.g. Bangalore, India, Remote)"
            disabled={loading || locations.length >= 4}
          />
          <button type="button" onClick={add} disabled={loading || !input.trim()} className="add-btn"><Plus size={14} /></button>
        </div>
      </div>
      {locations.length > 0 && (
        <div className="loc-chips">
          {locations.map(l => (
            <span key={l} className="loc-chip">{l} <button onClick={() => remove(l)}><X size={12} /></button></span>
          ))}
        </div>
      )}
      <div className="workmode-row">
        <span className="wm-label">Work mode (optional):</span>
        {['remote', 'hybrid', 'onsite'].map(m => (
          <button key={m} type="button" className={`wm-chip ${workMode === m ? 'active' : ''}`} onClick={() => setWorkMode(workMode === m ? '' : m)}>{m}</button>
        ))}
      </div>
      <button className="search-btn followup-submit" onClick={submit} disabled={loading || locations.length === 0}>Search with these locations</button>
      <p className="followup-hint">Add up to 4 — e.g. India, Delhi, Bangalore, Remote</p>
    </div>
  )
}
