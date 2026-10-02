import { useCallback, useEffect, useState } from 'react'
import { Bell, Trash2, Clock, Mail, Calendar, Plus, RefreshCw, Pencil, Pause, Play } from 'lucide-react'
import { getAlerts, deleteAlert, patchAlert } from './api'
import CollapsibleSection from './CollapsibleSection'
import ConfirmModal from './ConfirmModal'
import { pushToast } from './Toast'

// The account allows exactly one alert per user (unique index on user_id), so
// this is a single-alert panel rather than a list. Everything here is
// owner-scoped. The scheduled run route is service-key only, so the browser
// never triggers a run — that is left entirely to n8n.

function formatNextRun(iso) {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    const now = new Date()
    const isToday = d.toDateString() === now.toDateString()
    const tomorrow = new Date(now); tomorrow.setDate(now.getDate() + 1)
    const isTomorrow = d.toDateString() === tomorrow.toDateString()
    const time = d.toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit', hour12: true })
    const date = d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: d.getFullYear() !== now.getFullYear() ? 'numeric' : undefined })
    if (isToday) return `Today, ${time}`
    if (isTomorrow) return `Tomorrow, ${time}`
    return `${date}, ${time}`
  } catch { return iso }
}

function formatTimeDisplay(hhmm) {
  const [h, m] = (hhmm || '09:00').split(':').map(Number)
  const hour12 = h === 0 ? 12 : h > 12 ? h - 12 : h
  const ampm = h >= 12 ? 'PM' : 'AM'
  return `${hour12}:${String(m).padStart(2, '0')} ${ampm}`
}

// unwrap() sets err.code / err.detail; err.response never exists in this app.
const errText = (e, fallback) =>
  e?.detail?.message || e?.detail || e?.message || fallback

export default function MyAlerts({ onCreate, onEdit, onChange }) {
  const [alert, setAlert] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(null) // 'pause' | 'delete'
  const [confirmOpen, setConfirmOpen] = useState(false)

  // The header bell needs to know whether the user already has an alert so it
  // opens the form in edit rather than create mode. Every state change is
  // reported up.
  const applyAlert = useCallback((a) => {
    setAlert(a)
    onChange && onChange(a)
  }, [onChange])

  const fetchAlerts = useCallback(async () => {
    setLoading(true); setErr(null)
    try {
      const data = await getAlerts()
      const list = data.alerts || []
      applyAlert(list.length ? list[0] : null)
    } catch (e) {
      setErr(errText(e, 'Failed to load your alert'))
    } finally { setLoading(false) }
  }, [applyAlert])

  useEffect(() => { fetchAlerts() }, [fetchAlerts])

  const handleToggleActive = async () => {
    const next = !alert.is_active
    setBusy('pause')
    try {
      const res = await patchAlert({ is_active: next })
      if (res.alert) applyAlert(res.alert)
      pushToast(next ? 'Alert resumed' : 'Alert paused', 'success')
    } catch (e) {
      pushToast(errText(e, 'Could not change the alert state'), 'error')
    } finally { setBusy(null) }
  }

  const handleDelete = async () => {
    setBusy('delete')
    try {
      await deleteAlert()
      applyAlert(null)
      setConfirmOpen(false)
      pushToast('Alert deleted', 'success')
    } catch (e) {
      pushToast(errText(e, 'Delete failed'), 'error')
    } finally { setBusy(null) }
  }

  if (loading) {
    return (
      <div className="my-alerts my-alerts-compact">
        <div className="my-alerts-head">
          <Bell size={16} />
          <span className="my-alerts-title">Job alert</span>
          <span className="spinner-small" />
        </div>
      </div>
    )
  }

  // No alert yet: a single call to action, no fold control — there is nothing
  // to collapse and a header that only says "create" would be noise.
  if (!alert) {
    return (
      <div className="my-alerts my-alerts-compact">
        <button className="my-alerts-head my-alerts-toggle" onClick={onCreate} title="Create a job alert">
          <Bell size={15} />
          <span>Job alert</span>
          <span className="my-alerts-count">none yet — create one</span>
          <Plus size={15} />
        </button>
        {err && <div className="alert-error alert-error-pad">{err}</div>}
      </div>
    )
  }

  const paused = !alert.is_active
  const roles = alert.queries?.length ? alert.queries : [alert.query]
  const locs = alert.locations?.length ? alert.locations : [alert.location]
  const searchCount = roles.length * locs.length
  // Shown on the collapsed header, so the state is readable while folded.
  const stateLine = paused
    ? 'Paused'
    : `${alert.frequency} at ${formatTimeDisplay(alert.time)} · ${formatNextRun(alert.next_run_at)}`

  // Label/value cells. A grid reads faster than the old run of chip rows and
  // mixed meta lines, and it collapses to one column on a narrow screen.
  const field = (label, value) => (
    <div className="alert-field" key={label}>
      <span className="alert-field-label">{label}</span>
      <span className="alert-field-value">{value}</span>
    </div>
  )

  return (
    <CollapsibleSection
      id="alerts"
      icon={Bell}
      title="Job alert"
      summary={stateLine}
      defaultOpen={false}
      className="csec-alerts"
    >
      <div className="my-alerts">
        <div className="my-alerts-head">
          <span className={`alert-state-badge${paused ? ' is-paused' : ''}`}>
            {paused ? 'Paused' : 'Active'}
          </span>
          <span className="my-alerts-count">
            {paused ? 'no runs scheduled' : `${searchCount} search${searchCount === 1 ? '' : 'es'} per run`}
          </span>
          {/* Only refresh here. Edit lives with the other actions below — having
              both a pencil in the header and an Edit button duplicated the action. */}
          <button className="alert-refresh" onClick={fetchAlerts} title="Refresh" aria-label="Refresh">
            <RefreshCw size={14} />
          </button>
        </div>

        {err && <div className="alert-error alert-error-pad">{err}</div>}

        <div className={`alert-card${paused ? ' alert-card-paused' : ''}`}>
          <div className="alert-fields">
            {field(
              'Roles',
              <span className="alert-card-locs">
                {roles.map(r => <span key={r} className="role-chip">{r}</span>)}
              </span>
            )}
            {field(
              'Locations',
              <span className="alert-card-locs">
                {locs.map(l => <span key={l} className="loc-chip">{l}</span>)}
              </span>
            )}
            {field('Experience', alert.experience || 'Any level')}
            {field(
              'Schedule',
              <span className="alert-schedule">
                <Calendar size={12} />
                <span style={{ textTransform: 'capitalize' }}>{alert.frequency}</span>
                <span aria-hidden="true">·</span>
                {formatTimeDisplay(alert.time)} IST
              </span>
            )}
            {field('Delivers to', <span className="alert-mail"><Mail size={12} />{alert.email}</span>)}
            {field(
              'Next run',
              paused
                ? <span className="alert-muted">Paused</span>
                : <span className="alert-runline"><Clock size={12} />{formatNextRun(alert.next_run_at)}</span>
            )}
            {alert.last_run_at && field(
              'Last run',
              <span className="alert-runline">
                <Clock size={12} />
                {formatNextRun(alert.last_run_at)}
                <span className="alert-muted">
                  {' · '}{alert.sent_count} job{alert.sent_count === 1 ? '' : 's'} sent
                </span>
              </span>
            )}
          </div>

          <div className="alert-card-actions">
            <button
              className="job-btn ghost"
              onClick={handleToggleActive}
              disabled={busy === 'pause'}
            >
              {paused
                ? <><Play size={12} /> Resume</>
                : <><Pause size={12} /> Pause</>}
            </button>
            <button className="job-btn ghost" onClick={onEdit} disabled={busy === 'delete'}>
              <><Pencil size={12} /> Edit</>
            </button>
            <button className="job-btn primary" onClick={() => setConfirmOpen(true)} disabled={busy === 'delete'}>
              <><Trash2 size={12} /> Delete</>
            </button>
          </div>
        </div>
      </div>

      <ConfirmModal
        open={confirmOpen}
        title="Delete job alert?"
        message="Notifications stop. The alert is removed from your account — you can always create a new one."
        confirmText="Delete alert"
        onConfirm={handleDelete}
        onCancel={() => setConfirmOpen(false)}
        loading={busy === 'delete'}
      />
    </CollapsibleSection>
  )
}
