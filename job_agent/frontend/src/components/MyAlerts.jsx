import { useEffect, useState } from 'react'
import { Bell, Trash2, Zap, Clock, Mail, MapPin, Calendar } from 'lucide-react'
import { getAlerts, deleteAlert, runAlert } from '../api/jobs'
import ConfirmModal from './ConfirmModal'
import { pushToast } from './Toast'

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
  const [h, m] = hhmm.split(':').map(Number)
  const hour12 = h === 0 ? 12 : h > 12 ? h - 12 : h
  const ampm = h >= 12 ? 'PM' : 'AM'
  return `${hour12}:${String(m).padStart(2,'0')} ${ampm}`
}

export default function MyAlerts({ refreshKey, onViewJobs }) {
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(null)
  const [runState, setRunState] = useState({}) // alert_id -> {loading, result, error}
  const [deleteId, setDeleteId] = useState(null)
  const [confirmId, setConfirmId] = useState(null)

  const fetchAlerts = async () => {
    setLoading(true); setErr(null)
    try {
      const data = await getAlerts()
      setAlerts(data.alerts || [])
    } catch (e) {
      setErr(e.response?.data?.detail || e.message || 'Failed to load alerts')
    } finally { setLoading(false) }
  }

  useEffect(() => { fetchAlerts() }, [refreshKey])

  const handleDelete = async (id) => {
    setDeleteId(id)
    try {
      await deleteAlert(id)
      setAlerts(a => a.filter(x => x.id !== id))
      pushToast('Alert deleted', 'success')
    } catch (e) {
      pushToast(e.response?.data?.detail || e.message || 'Delete failed', 'error')
    } finally { setDeleteId(null); setConfirmId(null) }
  }

  const handleRun = async (id) => {
    setRunState(s => ({ ...s, [id]: { loading: true, result: null, error: null } }))
    try {
      const res = await runAlert(id)
      setRunState(s => ({ ...s, [id]: { loading: false, result: res, error: null } }))
      fetchAlerts()
      if (res.count > 0) {
        pushToast(`${res.count} fresh job${res.count>1?'s':''} found`, 'success')
        if (onViewJobs) onViewJobs(res.new_jobs)
      } else {
        pushToast('No new jobs — all caught up', 'success')
      }
    } catch (e) {
      const msg = e.response?.data?.detail || e.message || 'Run failed'
      setRunState(s => ({ ...s, [id]: { loading: false, result: null, error: msg } }))
      pushToast(msg, 'error')
    }
  }

  if (loading && alerts.length === 0) {
    return (
      <div className="my-alerts">
        <div className="my-alerts-head"><Bell size={16} /> MY JOB ALERTS</div>
        <div className="alert-skeleton">Loading alerts…</div>
      </div>
    )
  }

  return (
    <div className="my-alerts">
      <div className="my-alerts-head">
        <span><Bell size={16} style={{ verticalAlign: 'middle', marginRight: '.35rem' }} />MY JOB ALERTS</span>
        <span className="my-alerts-count">{alerts.length} active</span>
        <button className="alert-refresh" onClick={fetchAlerts} title="Refresh">↻</button>
      </div>

      {err && <div className="alert-error" style={{ marginBottom: '.6rem' }}>{err}</div>}

      {alerts.length === 0 ? (
        <div className="my-alerts-empty">
          <Bell size={20} color="#94a3b8" />
          <p>No alerts yet</p>
          <span>Create one to get daily fresh jobs at your time — pre-auth uses email field directly.</span>
        </div>
      ) : (
        <div className="alert-grid">
          {alerts.map(a => {
            const rs = runState[a.id]
            return (
              <div key={a.id} className="alert-card">
                <div className="alert-card-top">
                  <div className="alert-card-title"><Bell size={14} /> {a.query}</div>
                  <div className="alert-card-meta"><MapPin size={12} /> {a.location} · {a.experience || '—'} </div>
                  <div className="alert-card-meta"><Calendar size={12} /> <span style={{ textTransform: 'capitalize' }}>{a.frequency}</span> · {formatTimeDisplay(a.time)} IST</div>
                  <div className="alert-card-meta"><Mail size={12} /> {a.email}</div>
                </div>
                <div className="alert-card-mid">
                  <div className="alert-next"><Clock size={12} /> Next run: {formatNextRun(a.next_run_at)}</div>
                  {a.last_run_at && <div className="alert-last">Last: {formatNextRun(a.last_run_at)} · Sent: {a.sent_job_ids.length} jobs</div>}
                </div>

                {rs?.result && (
                  <div className="alert-run-result">
                    {rs.result.count > 0 ? (
                      <span className="run-ok">✓ {rs.result.count} new job{rs.result.count>1?'s':''} · fetched {rs.result.total_fetched} · filtered {rs.result.filtered_fresh} old</span>
                    ) : (
                      <span className="run-empty">No new jobs — all fresh already sent ({rs.result.filtered_duplicate} dupes skipped)</span>
                    )}
                  </div>
                )}
                {rs?.error && <div className="alert-error">{rs.error}</div>}

                <div className="alert-card-actions">
                  <button
                    className="job-btn ghost prepare"
                    onClick={() => handleRun(a.id)}
                    disabled={rs?.loading}
                    title="Run via Job Agent now — fresh + unique"
                  >
                    {rs?.loading ? <span className="btn-loading"><span className="spinner-small" /> Running</span> : <><Zap size={12} /> Run Now</>}
                  </button>
                  <button
                    className="job-btn primary"
                    onClick={() => setConfirmId(a.id)}
                    disabled={deleteId === a.id}
                  >
                    <><Trash2 size={12} /> Delete</>
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
      <ConfirmModal
        open={!!confirmId}
        title="Delete alert?"
        message="This will stop notifications for this alert. Sent history stays on server."
        confirmText="Delete alert"
        onConfirm={() => handleDelete(confirmId)}
        onCancel={() => setConfirmId(null)}
        loading={!!deleteId}
      />
    </div>
  )
}
