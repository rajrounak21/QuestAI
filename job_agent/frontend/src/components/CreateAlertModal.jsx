import { useState, useEffect } from 'react'
import { X, Bell, Mail, MapPin, Briefcase, Clock, CheckCircle } from 'lucide-react'
import { createAlert } from '../api/jobs'
import { pushToast } from './Toast'

const EXPERIENCES = ['Fresher', '0-1 years', '1-3 years', '3-5 years', '5+ years']

export default function CreateAlertModal({ isOpen, onClose, onCreated, defaultQuery = '', defaultLocation = '' }) {
  const [query, setQuery] = useState(defaultQuery)
  const [location, setLocation] = useState(defaultLocation || 'India')
  const [experience, setExperience] = useState('0-1 years')
  const [email, setEmail] = useState(localStorage.getItem('alert_email') || 'rajrounak366@gmail.com')
  const [frequency, setFrequency] = useState('daily')
  const [time, setTime] = useState('09:00')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)

  useEffect(() => {
    if (isOpen) {
      setQuery(defaultQuery || '')
      setLocation(defaultLocation || 'India')
      setError(null)
      setSuccess(null)
    }
  }, [isOpen, defaultQuery, defaultLocation])

  if (!isOpen) return null

  const validate = () => {
    if (!query.trim()) return 'Job role / keywords is required'
    if (!location.trim()) return 'Location is required'
    if (!email.trim() || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return 'Valid email is required'
    if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(time)) return 'Time must be HH:MM (e.g. 09:00)'
    return null
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const v = validate()
    if (v) { setError(v); return }
    setLoading(true); setError(null)
    try {
      const res = await createAlert({
        query: query.trim(),
        location: location.trim(),
        experience: experience || null,
        frequency,
        time,
        email: email.trim(),
      })
      localStorage.setItem('alert_email', email.trim())
      pushToast('Job alert created — next run scheduled', 'success')
      setSuccess({
        alert_id: res.alert_id,
        query: query.trim(),
        location: location.trim(),
        experience,
        frequency,
        time,
        email: email.trim(),
      })
      onCreated && onCreated()
    } catch (err) {
      const msg = err.response?.data?.detail || err.response?.data?.error || err.message || 'Failed to create alert'
      let text = ''
      if (Array.isArray(msg)) text = msg.map(m => m.msg).join(' • ')
      else if (typeof msg === 'string') text = msg
      else text = JSON.stringify(msg)
      setError(text)
      pushToast(text, 'error')
    } finally { setLoading(false) }
  }

  const formatNext = () => {
    // next_run = tomorrow at time if today time passed — mirror backend
    // simplified display for success
    const [h, m] = time.split(':').map(Number)
    const hour12 = h === 0 ? 12 : h > 12 ? h - 12 : h
    const ampm = h >= 12 ? 'PM' : 'AM'
    const mm = String(m).padStart(2, '0')
    return `Tomorrow at ${hour12}:${mm} ${ampm}`
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
                <h3 className="modal-title">Create Job Alert</h3>
                <p className="modal-sub">Get fresh jobs daily at your time — no spam, only new jobs.</p>
              </div>
            </div>

            <form onSubmit={handleSubmit} className="alert-form">
              <label className="alert-label"><Briefcase size={12} /> Job role / keywords *</label>
              <input
                className="alert-input"
                placeholder="AI Engineer Intern"
                value={query}
                onChange={e => setQuery(e.target.value)}
                disabled={loading}
              />

              <label className="alert-label"><MapPin size={12} /> Location *</label>
              <input
                className="alert-input"
                placeholder="India"
                value={location}
                onChange={e => setLocation(e.target.value)}
                disabled={loading}
              />

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
              <span className="alert-hint">Pre-auth: email stored locally. Later taken from login.</span>

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
                {loading ? <span className="btn-loading"><span className="spinner-small" /> Creating</span> : 'Create Alert'}
              </button>
            </form>
          </>
        ) : (
          <div className="alert-success">
            <div className="alert-success-icon"><CheckCircle size={36} color="#10b981" /></div>
            <h3 className="alert-success-title">✅ Job alert created</h3>
            <div className="alert-success-card">
              <div className="alert-success-row"><strong>{success.query}</strong></div>
              <div className="alert-success-meta">{success.location} · {success.experience}</div>
              <div className="alert-success-meta" style={{ textTransform: 'capitalize' }}>{success.frequency} at {success.time} IST</div>
              <div className="alert-success-meta"><Mail size={12} style={{ display: 'inline', verticalAlign: 'middle' }} /> {success.email}</div>
              <div className="alert-success-next">Next alert: {formatNext()}</div>
              <div className="alert-success-id">ID: {success.alert_id}</div>
            </div>
            <div style={{ display: 'flex', gap: '.5rem', marginTop: '.9rem' }}>
              <button className="job-btn primary" style={{ flex: 1 }} onClick={onClose}>Done</button>
              <button className="job-btn" style={{ flex: 1 }} onClick={() => { setSuccess(null); setQuery('') }}>Create another</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
