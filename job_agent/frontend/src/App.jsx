import { useState, useMemo } from 'react'
import { Briefcase, SlidersHorizontal, Zap, Bell } from 'lucide-react'
import JobSearch from './components/JobSearch'
import JobCard from './components/JobCard'
import JobDetails from './components/JobDetails'
import InlineJobSearch from './components/InlineJobSearch'
import PrepareApplication from './components/PrepareApplication'
import JobFilters from './components/JobFilters'
import EmptyState from './components/EmptyState'
import SearchProgress from './components/SearchProgress'
import MissingInfoModal from './components/MissingInfoModal'
import CreateAlertModal from './components/CreateAlertModal'
import MyAlerts from './components/MyAlerts'
import ToastContainer from './components/Toast'
import { searchJobs } from './api/jobs'
import './App.css'

const DEFAULT_FILTERS = { company: [], location: [], freshness: [], employment: [], sortBy: 'freshness' }

const freshnessRank = { 'Today': 0, '1 day ago': 1, '3 days ago': 2, '1 week ago': 3, 'Older': 4, 'Unknown': 5 }

export default function App() {
  const [jobs, setJobs] = useState([])
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [followUp, setFollowUp] = useState(null)
  const [hasSearched, setHasSearched] = useState(false)
  const [progressSteps, setProgressSteps] = useState([])
  const [filters, setFilters] = useState({ ...DEFAULT_FILTERS })
  const [lastQuery, setLastQuery] = useState('')
  const [lastResume, setLastResume] = useState(null)
  const [selectedJob, setSelectedJob] = useState(null)
  const [prepareJob, setPrepareJob] = useState(null)
  const [sessionId, setSessionId] = useState(() => localStorage.getItem('job_session_id') || null)
  const [showAlertModal, setShowAlertModal] = useState(false)
  const [alertRefresh, setAlertRefresh] = useState(0)
  const [alertRunJobs, setAlertRunJobs] = useState(null)

  const doSearch = async ({ query, resumeFile, locations, session }) => {
    setLoading(true)
    setError(null)
    setFollowUp(null)
    const sid = session || sessionId
    if (!locations || locations.split(',').length <= 4) {
      // keep existing jobs until new results, but mark searched
      if (!locations) {
        setJobs([])
        setProfile(null)
        setFilters({ ...DEFAULT_FILTERS })
      }
      setHasSearched(true)
    }
    setProgressSteps(['Analyzing input…'])

    // keep for followup
    if (query !== undefined) setLastQuery(query)
    if (resumeFile !== undefined) setLastResume(resumeFile)

    try {
      const locStr = locations || undefined
      const q = query ?? lastQuery
      const rf = resumeFile ?? lastResume
      const data = await searchJobs({ query: q, resumeFile: rf, locations: locStr, sessionId: sid })
      if (data.session_id) {
        setSessionId(data.session_id)
        localStorage.setItem('job_session_id', data.session_id)
      }
      setProgressSteps(data.progress_steps || [])
      if (data.error) setError(data.error)
      else if (data.follow_up_question) {
        setFollowUp(data.follow_up_question)
        setProfile(data.profile || null)
      } else {
        setJobs(data.jobs || [])
        setProfile(data.profile || null)
      }
    } catch (err) {
      console.error(err)
      const msg = err.response?.data?.error || err.response?.data?.detail || err.message || 'Search failed'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = (obj) => doSearch(obj)
  const handleFollowUp = (payload) => {
    // payload can be {query, locations} (role follow-up) or {locations} (location follow-up)
    if (typeof payload === 'string') {
      // legacy: string is locations
      return doSearch({ query: lastQuery, resumeFile: lastResume, locations: payload })
    }
    const nextQuery = payload.query !== undefined ? payload.query : lastQuery
    const nextLocations = payload.locations !== undefined ? payload.locations : undefined
    return doSearch({ query: nextQuery, resumeFile: lastResume, locations: nextLocations })
  }

  const filtered = useMemo(() => {
    let res = [...jobs]
    if (filters.company.length) res = res.filter(j => filters.company.includes(j.company))
    if (filters.freshness.length) res = res.filter(j => filters.freshness.includes(j.freshness_bucket || 'Unknown'))
    if (filters.employment.length) res = res.filter(j => filters.employment.includes(j.employment_type || 'Not specified'))
    if (filters.location.length) {
      res = res.filter(j => {
        const loc0 = (j.location || 'Unknown').split(',')[0].trim()
        return filters.location.includes(loc0)
      })
    }
    if (filters.sortBy === 'freshness') res.sort((a, b) => (freshnessRank[a.freshness_bucket] ?? 5) - (freshnessRank[b.freshness_bucket] ?? 5))
    return res
  }, [jobs, filters])

  return (
    <div className="app">
      <header className="app-header premium">
        <div className="header-inner">
          <div className="brand">
            <div className="brand-mark has-logo"><img src="/logo.png" alt="QuestAI" /></div>
            <div>
              <h1>QuestAI</h1>
              <p className="header-sub">Job Agent · Fresh · Personalized · Alert-ready</p>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '.6rem', alignItems: 'center' }}>
            <button className="alert-header-btn" onClick={() => setShowAlertModal(true)}><Bell size={14} /> Create Job Alert</button>
            <div className="header-pill">Google Jobs • Live • 2-3 queries • deduped</div>
          </div>
        </div>
      </header>

      <main className="app-main">
        <JobSearch onSearch={handleSearch} loading={loading} />

        {/* Alert management — My Alerts + Create CTA */}
        <MyAlerts refreshKey={alertRefresh} onViewJobs={(newJobs) => {
          // Run Now produced fresh jobs — show them inline as results
          if (newJobs?.length) {
            setAlertRunJobs(newJobs)
            setJobs(newJobs)
            setHasSearched(true)
            setError(null)
            // scroll to results
            setTimeout(() => window.scrollTo({ top: 600, behavior: 'smooth' }), 150)
          }
        }} />
        {alertRunJobs && (
          <div className="alert-run-banner">
            <Zap size={14} /> Alert run returned <strong>{alertRunJobs.length}</strong> fresh job{alertRunJobs.length>1?'s':''} — showing below. They match your alert's fresh + unique filter.
            <button className="job-btn primary" style={{ marginLeft: 'auto' }} onClick={() => setAlertRunJobs(null)}>Clear</button>
          </div>
        )}

        <SearchProgress loading={loading} steps={progressSteps} />

        {profile && !loading && (
          <div className="profile-bar">
            <span className="profile-label">Profile:</span>
            {profile.target_roles?.length > 0 && <span className="profile-chip">{profile.target_roles.join(' / ')}</span>}
            {profile.locations?.length > 0 && <span className="profile-chip loc">{profile.locations.join(', ')}</span>}
            {profile.work_mode?.length > 0 && <span className="profile-chip mode">{profile.work_mode.join(', ')}</span>}
            {profile.skills?.slice(0, 5).map(s => <span key={s} className="profile-chip skill">{s}</span>)}
          </div>
        )}

        {error && <EmptyState error={error} />}
        {/* inline follow-up replaced by modal — keeps UI clean, collects role 2-3 + locations together */}
        {followUp && (
          <MissingInfoModal
            question={followUp}
            profile={profile}
            resumeName={lastResume?.name || null}
            onClose={() => setFollowUp(null)}
            onSubmit={(payload) => {
              setFollowUp(null)
              handleFollowUp(payload)
            }}
            loading={loading}
          />
        )}

        {!loading && !error && !followUp && hasSearched && jobs.length === 0 && <EmptyState />}

        {!loading && jobs.length > 0 && !followUp && (
          <>
            <InlineJobSearch
              onSearch={({ role, location }) => {
                const q = role || ''
                const locs = location || ''
                // reuse session, keep resume memory
                doSearch({ query: q || lastQuery, resumeFile: null, locations: locs || undefined, session: sessionId })
              }}
              loading={loading}
              defaultRole={profile?.target_roles?.[0] || ''}
              defaultLocation={profile?.locations?.[0] || ''}
            />
            <div className="results-container">
              <div className="results-sidebar">
                <JobFilters jobs={jobs} filters={filters} onFilterChange={setFilters} />
              </div>
              <div className="results-main">
                <div className="results-toolbar">
                <div className="results-count"><span className="count-strong">{filtered.length}</span> of {jobs.length} jobs {filters.company.length || filters.location.length ? <span className="filtered-dot">• filtered</span> : null}</div>
                <div className="toolbar-actions">
                  <span className="toolbar-label">Sort:</span>
                  <select value={filters.sortBy} onChange={e => setFilters({ ...filters, sortBy: e.target.value })} className="toolbar-select">
                    <option value="freshness">Freshest first</option>
                    <option value="relevance">Relevance</option>
                  </select>
                </div>
              </div>
              {filtered.length === 0 ? <div className="no-results premium"><SlidersHorizontal size={16} /> No jobs match filters. Clear or adjust.</div> : (
                <div className="job-grid">
                  {filtered.map(job => <JobCard key={job.id} job={job} onSelect={setSelectedJob} onPrepare={setPrepareJob} />)}
                </div>
              )}
            </div>
            </div>
          </>
        )}

        {!hasSearched && !loading && (
          <div className="hero-empty">
            <h2>Find fresh, real jobs</h2>
            <p>Upload resume (PDF, 1-2 pages) + query — e.g. “AI/ML or Python backend internships in India, preferably remote.” We fetch live Google Jobs, dedupe, fresh-first.</p>
          </div>
        )}
      </main>
      {selectedJob && <JobDetails job={selectedJob} onClose={() => setSelectedJob(null)} onPrepare={(j) => { setSelectedJob(null); setPrepareJob(j); }} />}
      {prepareJob && <PrepareApplication sessionId={sessionId} job={prepareJob} onClose={() => setPrepareJob(null)} />}
      {showAlertModal && (
        <CreateAlertModal
          isOpen={showAlertModal}
          onClose={() => setShowAlertModal(false)}
          defaultQuery={profile?.target_roles?.[0] || lastQuery || ''}
          defaultLocation={profile?.locations?.[0] || ''}
          onCreated={() => setAlertRefresh(k => k + 1)}
        />
      )}
      <ToastContainer />
    </div>
  )
}
