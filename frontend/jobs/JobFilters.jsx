import { useMemo, useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'

export default function JobFilters({ jobs, filters, onFilterChange }) {
  const [open, setOpen] = useState({ company: true, location: true, freshness: true, employment: true })

  const counts = useMemo(() => {
    const company = {}
    const location = {}
    const freshness = {}
    const employment = {}
    for (const j of jobs) {
      company[j.company] = (company[j.company] || 0) + 1
      const loc = (j.location || 'Unknown').split(',')[0].trim() || 'Unknown'
      location[loc] = (location[loc] || 0) + 1
      const fb = j.freshness_bucket || 'Unknown'
      freshness[fb] = (freshness[fb] || 0) + 1
      const et = j.employment_type || 'Not specified'
      employment[et] = (employment[et] || 0) + 1
    }
    return { company, location, freshness, employment }
  }, [jobs])

  const toggle = (key, val) => {
    const list = filters[key] || []
    const next = list.includes(val) ? list.filter(v => v !== val) : [...list, val]
    onFilterChange({ ...filters, [key]: next })
  }

  const Section = ({ id, title, entries }) => (
    <div className="filter-section">
      <button type="button" className="filter-head" onClick={() => setOpen(o => ({ ...o, [id]: !o[id] }))}>
        {title} {open[id] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>
      {open[id] && (
        <div className="filter-options">
          {Object.entries(entries).sort((a, b) => b[1] - a[1]).slice(0, 6).map(([name, c]) => (
            <label key={name} className="filter-option">
              <input type="checkbox" checked={(filters[id] || []).includes(name)} onChange={() => toggle(id, name)} />
              <span className="opt-name">{name}</span>
              <span className="opt-count">{c}</span>
            </label>
          ))}
          {Object.keys(entries).length === 0 && <span className="muted">No data</span>}
        </div>
      )}
    </div>
  )

  return (
    <div className="filter-panel">
      {/* No heading here: the panel now lives inside a CollapsibleSection that
          already says "Filters", and the two titles read as a bug. */}
      {(filters.company?.length || filters.location?.length || filters.freshness?.length || filters.employment?.length) ? (
        <button type="button" className="clear-filters" onClick={() => onFilterChange({ company: [], location: [], freshness: [], employment: [], sortBy: filters.sortBy || 'freshness' })}>Clear all</button>
      ) : null}
      <Section id="company" title="Company" entries={counts.company} />
      <Section id="location" title="Location" entries={counts.location} />
      <Section id="freshness" title="Posted" entries={counts.freshness} />
      <Section id="employment" title="Employment" entries={counts.employment} />
    </div>
  )
}
