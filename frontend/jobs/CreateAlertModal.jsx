import { useState, useEffect } from 'react'
import { X, Bell, Mail, MapPin, Briefcase, Clock, CheckCircle, Plus } from 'lucide-react'
import { createAlert, patchAlert } from './api'
import { pushToast } from './Toast'

const EXPERIENCES = ['Fresher', '0-1 years', '1-3 years', '3-5 years', '5+ years']

// Must mirror MAX_ALERT_QUERIES / MAX_ALERT_LOCATIONS / MAX_ALERT_SEARCHES
// in backend/agents/job/schemas/alerts.py
const MAX_ROLES = 2
const MAX_LOCATIONS = 2
const MAX_SEARCHES = 4

// Accepts an array, a single string, or slash/comma-joined text so a profile
// value like "AI Engineer / ML Engineer" still becomes separate chips.
function toList(value) {
  if (Array.isArray(value)) return value
  if (typeof value === 'string') return value.split(/[,/]/)
  return []
}

function clean(values) {
  const out = []
  const seen = new Set()
  for (const v of toList(values)) {
    const s = (v || '').trim()
    if (!s) continue
    const k = s.toLowerCase()
    if (seen.has(k)) continue
    seen.add(k)
    out.push(s)
  }
  return out
}

export default function CreateAlertModal({
  isOpen,
  onClose,
  onSaved,
  defaultRoles = [],
  defaultLocations = [],
  // "create" for a new alert, "edit" when an existing one is being changed.
  mode = 'create',
  initial = null,
  accountEmail = '',
  // Fired when the server rejects the save because the resume is gone (409).
  // Jobs.jsx reopens the upload gate and replays this form.
  onResumeRequired,
}) {
  const [roles, setRoles] = useState([])
  const [locations, setLocations] = useState([])
  const [roleInput, setRoleInput] = useState('')
  const [locInput, setLocInput] = useState('')
  const [experience, setExperience] = useState('')
  // Prefilled from the signed-in account so the user does not have to type it.
  // The backend also defaults to it if this is sent empty.
  const [email, setEmail] = useState('')
  const [frequency, setFrequency] = useState('daily')
  const [time, setTime] = useState('09:00')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)

  useEffect(() => {
    if (!isOpen) return
    setRoleInput('')
    setLocInput('')
    setError(null)
    setSuccess(null)
    if (mode === 'edit' && initial) {
      setRoles(clean(initial.queries || initial.query).slice(0, MAX_ROLES))
      setLocations(clean(initial.locations || initial.location).slice(0, MAX_LOCATIONS))
      setExperience(initial.experience || '')
      setEmail(initial.email || accountEmail)
      setFrequency(initial.frequency || 'daily')
      setTime(initial.time || '09:00')
    } else {
      // A resume can carry more target_roles than an alert may hold. Cap here
      // too, not just in addRole — otherwise the form shows three chips while
      // telling the user the maximum is 2, and the server silently drops the
      // third.
      setRoles(clean(defaultRoles).slice(0, MAX_ROLES))
      const locs = clean(defaultLocations).slice(0, MAX_LOCATIONS)
      setLocations(locs.length ? locs : ['India'])
      setExperience('')
      setEmail(accountEmail)
      setFrequency('daily')
      setTime('09:00')
    }
  }, [isOpen, mode, initial, defaultRoles, defaultLocations, accountEmail])

  if (!isOpen) return null

  // One SerpApi call per role x location. At the 3x3 limit this is exactly
  // MAX_SEARCHES, so nothing is ever trimmed.
  const plannedSearches = Math.min(roles.length * locations.length, MAX_SEARCHES)

  const addRole = (raw) => {
    const parts = clean([raw])
    if (!parts.length) return
    setRoles((prev) => {
      const next = clean([...prev, ...parts])
      return next.slice(0, MAX_ROLES)
    })
    setRoleInput('')
  }

  const addLocation = (raw) => {
    const parts = clean([raw])
    if (!parts.length) return
    setLocations((prev) => {
      const next = clean([...prev, ...parts])
      return next.slice(0, MAX_LOCATIONS)
    })
    setLocInput('')
  }

  const removeRole = (r) => setRoles((prev) => prev.filter((x) => x !== r))
  const removeLocation = (l) => setLocations((prev) => prev.filter((x) => x !== l))

  const validate = () => {
    if (!roles.length) return 'Add at least one job role'
    if (!locations.length) return 'Add at least one location'
    if (!email.trim() || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return 'Valid email is required'
    if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(time)) return 'Time must be HH:MM (e.g. 09:00)'
    return null
  }

  const errText = (err) => {
    // unwrap() sets err.code / err.detail — there is no err.response anywhere in
    // this app, so reading it left the 409 resume-gate check below unreachable
    // and always fell through to the generic message.
    const detail = err?.detail
    const msg = detail?.message || detail?.error || err?.message || 'Request failed'
    if (Array.isArray(msg)) return msg.map(m => m.msg || JSON.stringify(m)).join(' • ')
    if (typeof msg === 'string') return msg
    return JSON.stringify(msg)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const v = validate()
    if (v) { setError(v); return }
    setLoading(true); setError(null)
    const payload = {
      queries: roles,
      locations,
      experience: experience || null,
      frequency,
      time,
      email: email.trim(),
    }
    try {
      if (mode === 'edit') {
        // PATCH only sends what the user can change. `sent` and alert_id are
        // never in a PATCH body, so already-emailed jobs stay suppressed.
        const res = await patchAlert(payload)
        const saved = res.alert || {}
        pushToast('Job alert updated', 'success')
        setSuccess({ ...saved, roles, locations, plannedSearches })
        onSaved && onSaved(saved)
      } else {
        // Legacy single-value fields kept so older n8n workflows still read
        // something sensible.
        const res = await createAlert({ ...payload, query: roles[0], location: locations[0] })
        pushToast('Job alert created — next run scheduled', 'success')
        setSuccess({
          alert_id: res.alert_id,
          // The server computed the real next_run_at (IST-aware); use it rather
          // than re-deriving the schedule on the client.
          next_run_at: res.alert?.next_run_at,
          roles,
          locations,
          experience,
          frequency,
          time,
          email: email.trim(),
          plannedSearches,
        })
        onSaved && onSaved(res.alert || { alert_id: res.alert_id })
      }
    } catch (err) {
      const text = errText(err)
      // The server enforces "an alert needs a stored resume". If the profile
      // was removed under us, hand control back so the upload gate can open
      // instead of leaving the user staring at an error. unwrap() puts the HTTP
      // status on err.code, not err.response.
      if (err?.code === 409 && /resume/i.test(text)) {
        setError(null)
        onResumeRequired && onResumeRequired()
        return
      }
      setError(text)
      pushToast(text, 'error')
    } finally { setLoading(false) }
  }

  const chipField = ({ label, icon: Icon, items, setItems, input, setInput, onAdd, onRemove, placeholder, cap, chipClass }) => (
    <>
      <label className="alert-label"><Icon size={12} /> {label} *</label>
      <div className="chip-input-wrap">
        <input
          placeholder={placeholder}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter') { e.preventDefault(); onAdd(input) }
            else if (e.key === 'Backspace' && !input && items.length) onRemove(items[items.length - 1])
          }}
          disabled={loading || items.length >= cap}
        />
        <button
          type="button"
          className="add-btn"
          onClick={() => onAdd(input)}
          disabled={loading || items.length >= cap}
          title={items.length >= cap ? `Maximum ${cap}` : 'Add'}
        >
          <Plus size={16} />
        </button>
      </div>
      {items.length > 0 && (
        <div className="loc-chips" style={{ marginTop: '.4rem' }}>
          {items.map(it => (
            <span key={it} className={chipClass}>
              {it}
              <button type="button" onClick={() => onRemove(it)} disabled={loading} aria-label={`Remove ${it}`}>
                <X size={11} />
              </button>
            </span>
          ))}
        </div>
      )}
      {items.length >= cap && (
        <span className="alert-hint">Maximum {cap} reached — remove one to add another.</span>
      )}
    </>
  )

  // Prefer the server's own next_run_at. It is the authority on the schedule
  // (and on IST), so guessing "tomorrow at HH:MM" here could contradict it —
  // which is exactly how the panel and this summary used to disagree.
  const formatNext = () => {
    const iso = success?.next_run_at
    if (iso) {
      try {
        const d = new Date(iso)
        if (!Number.isNaN(d.getTime())) {
          const now = new Date()
          const time = d.toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit', hour12: true })
          const sameDay = d.toDateString() === now.toDateString()
          const tomorrow = new Date(now)
          tomorrow.setDate(now.getDate() + 1)
          if (sameDay) return `Today, ${time}`
          if (d.toDateString() === tomorrow.toDateString()) return `Tomorrow, ${time}`
          return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }) + `, ${time}`
        }
      } catch { /* fall through to the local approximation */ }
    }
    const [h, m] = time.split(':').map(Number)
    const hour12 = h === 0 ? 12 : h > 12 ? h - 12 : h
    const ampm = h >= 12 ? 'PM' : 'AM'
    return `Tomorrow at ${hour12}:${String(m).padStart(2, '0')} ${ampm}`
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card alert-modal" onClick={e => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}><X size={16} /></button>

        {!success ? (
          <>
            <div className="alert-modal-head">
              <div className="alert-icon"><Bell size={18} /></div>
              <div>
                <h3 className="modal-title">{mode === 'edit' ? 'Edit Job Alert' : 'Create Job Alert'}</h3>
                <p className="modal-sub">
                  {mode === 'edit'
                    ? 'Change the roles, locations or schedule — jobs already emailed stay suppressed.'
                    : 'Get fresh jobs at your time — no spam, only new jobs.'}
                </p>
              </div>
            </div>

            <form onSubmit={handleSubmit} className="alert-form">
              {chipField({
                label: 'Job roles *',
                icon: Briefcase,
                items: roles,
                input: roleInput,
                setInput: setRoleInput,
                onAdd: addRole,
                onRemove: removeRole,
                placeholder: 'AI Engineer — press Enter to add more',
                cap: MAX_ROLES,
                chipClass: 'role-chip',
              })}

              {chipField({
                label: 'Locations *',
                icon: MapPin,
                items: locations,
                input: locInput,
                setInput: setLocInput,
                onAdd: addLocation,
                onRemove: removeLocation,
                placeholder: 'Bangalore — press Enter to add more',
                cap: MAX_LOCATIONS,
                chipClass: 'loc-chip',
              })}

              {roles.length > 0 && locations.length > 0 && (
                <span className="alert-hint">
                  Each role is searched in every location:{' '}
                  <strong>{plannedSearches} search{plannedSearches === 1 ? '' : 'es'}</strong> per run
                  {' · '}up to {MAX_ROLES} roles × {MAX_LOCATIONS} locations
                </span>
              )}

              <label className="alert-label">Experience</label>
              <select className="alert-input" value={experience} onChange={e => setExperience(e.target.value)} disabled={loading}>
                {EXPERIENCES.map(o => <option key={o} value={o}>{o}</option>)}
              </select>

              <label className="alert-label"><Mail size={12} /> Email *</label>
              <input
                type="email"
                className="alert-input"
                placeholder="you@example.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                disabled={loading}
              />
              <span className="alert-hint">
                Pre-filled from your account. Change it to send the digest somewhere else.
              </span>

              <label className="alert-label">Frequency</label>
              <div className="alert-radio-row">
                <label className={`alert-radio ${frequency === 'daily' ? 'active' : ''}`}>
                  <input type="radio" name="freq" value="daily" checked={frequency === 'daily'} onChange={() => setFrequency('daily')} /> Daily
                </label>
                <label className={`alert-radio ${frequency === 'weekly' ? 'active' : ''}`}>
                  <input type="radio" name="freq" value="weekly" checked={frequency === 'weekly'} onChange={() => setFrequency('weekly')} /> Weekly
                </label>
              </div>

              <label className="alert-label"><Clock size={12} /> Alert time (IST) *</label>
              <input
                type="time"
                className="alert-input"
                value={time}
                onChange={e => setTime(e.target.value)}
                disabled={loading}
              />

              {error && <div className="alert-error">{error}</div>}

              <button type="submit" disabled={loading} className="search-btn" style={{ width: '100%', marginTop: '.6rem', justifyContent: 'center' }}>
                {loading ? (
                  <span className="btn-loading">
                    <span className="spinner-small" /> {mode === 'edit' ? 'Saving' : 'Creating'}
                  </span>
                ) : (mode === 'edit' ? 'Save changes' : 'Create Alert')}
              </button>
            </form>
          </>
        ) : (
          <div className="alert-success">
            <div className="alert-success-icon"><CheckCircle size={36} color="#10b981" /></div>
            <h3 className="alert-success-title">
              {mode === 'edit' ? '✅ Job alert updated' : '✅ Job alert created'}
            </h3>
            <div className="alert-success-card">
              <div className="alert-success-row"><strong>{roles.length} role{roles.length === 1 ? '' : 's'}</strong></div>
              <div className="loc-chips">
                {roles.map(r => <span key={r} className="role-chip">{r}</span>)}
              </div>
              <div className="alert-success-row"><strong>{locations.length} location{locations.length === 1 ? '' : 's'}</strong></div>
              <div className="loc-chips">
                {locations.map(l => <span key={l} className="loc-chip">{l}</span>)}
              </div>
              {experience && <div className="alert-success-meta">{experience}</div>}
              <div className="alert-success-meta" style={{ textTransform: 'capitalize' }}>
                {success.frequency} at {success.time} IST
              </div>
              <div className="alert-success-meta">
                <Mail size={12} style={{ display: 'inline', verticalAlign: 'middle' }} /> {success.email}
              </div>
              <div className="alert-success-next">Next alert: {formatNext()} · {plannedSearches} searches per run</div>
              {success.alert_id && <div className="alert-success-id">ID: {success.alert_id}</div>}
            </div>
            <div className="alert-success-actions">
              <button className="job-btn primary" onClick={onClose}>Done</button>
            </div>
            {/* No "Create another": the account allows exactly one alert. A
                second create would just come back 409. To change anything the
                user edits the existing one. */}
            {mode === 'create' && (
              <p className="alert-success-note">
                You can edit roles, locations or the schedule any time — this stays your one alert.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
