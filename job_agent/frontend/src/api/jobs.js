import axios from 'axios'

const API_BASE = 'http://127.0.0.1:8000'

const api = axios.create({
  baseURL: API_BASE,
})

export async function searchJobs({ query, resumeFile, locations, sessionId }) {
  const form = new FormData()
  if (query) form.append('query', query)
  if (resumeFile) form.append('resume', resumeFile)
  if (locations) form.append('locations', locations)
  if (sessionId) form.append('session_id', sessionId)
  const headers = { 'Content-Type': 'multipart/form-data' }
  if (sessionId) headers['x-session-id'] = sessionId
  const res = await api.post('/api/jobs/search', form, {
    headers,
    timeout: 120000,
  })
  return res.data
}

export async function searchJobsJson({ query, locations, sessionId }) {
  const res = await api.post('/api/jobs/search-json', { query, locations, session_id: sessionId }, { timeout: 120000 })
  return res.data
}

export async function prepareApplication({ sessionId, job, force = false }) {
  const res = await api.post('/api/jobs/prepare', { session_id: sessionId, job_id: job.id, job, force }, { timeout: 60000 })
  return res.data
}

export async function generateCv({ sessionId, job, analysis }) {
  const res = await api.post('/api/jobs/generate-cv', { session_id: sessionId, job_id: job.id, job, analysis }, { responseType: 'blob', timeout: 60000 })
  return res.data
}

export async function checkHealth() {
  const res = await api.get('/health')
  return res.data
}

// ── Job Alert API (Phase 1 — in-memory, no auth) ──
export async function createAlert(payload) {
  const res = await api.post('/api/jobs/alerts', payload)
  return res.data
}
export async function getAlerts() {
  const res = await api.get('/api/jobs/alerts')
  return res.data
}
export async function getAlert(alertId) {
  const res = await api.get(`/api/jobs/alerts/${alertId}`)
  return res.data
}
export async function deleteAlert(alertId) {
  const res = await api.delete(`/api/jobs/alerts/${alertId}`)
  return res.data
}
export async function runAlert(alertId) {
  const res = await api.post(`/api/jobs/alerts/${alertId}/run`)
  return res.data
}
export async function getDueAlerts(now) {
  const res = await api.get('/api/jobs/alerts/due', { params: now ? { now } : {} })
  return res.data
}
