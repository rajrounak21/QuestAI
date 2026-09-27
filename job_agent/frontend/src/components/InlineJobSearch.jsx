import { useState } from 'react'
import { Search } from 'lucide-react'

export default function InlineJobSearch({ onSearch, loading, defaultRole, defaultLocation }) {
  const [role, setRole] = useState(defaultRole || '')
  const [loc, setLoc] = useState(defaultLocation || '')

  const submit = (e) => {
    e.preventDefault()
    if (!role.trim() && !loc.trim()) return
    onSearch({ role: role.trim(), location: loc.trim() })
  }

  return (
    <form className="inline-search" onSubmit={submit}>
      <div className="inline-inputs">
        <div className="inline-field">
          <input
            value={role}
            onChange={(e) => setRole(e.target.value)}
            placeholder="Job role — e.g. GenAI Intern"
            disabled={loading}
          />
        </div>
        <div className="inline-field loc">
          <input
            value={loc}
            onChange={(e) => setLoc(e.target.value)}
            placeholder="Location — e.g. Patna, Remote"
            disabled={loading}
            onKeyDown={(e) => { if (e.key === 'Enter' && !role.trim()) e.preventDefault() }}
          />
        </div>
        <button type="submit" className="inline-btn" disabled={loading || (!role.trim() && !loc.trim())}>
          <Search size={14} /> Search
        </button>
      </div>
      <p className="inline-hint">Quick search — keeps your skills in memory · Enter for fast search (no LLM if simple)</p>
    </form>
  )
}
