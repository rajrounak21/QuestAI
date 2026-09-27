import { useState, useEffect } from 'react'
import { Check, AlertTriangle, Briefcase, Award, Sparkles, Download, Eye, RefreshCw } from 'lucide-react'
import { prepareApplication, generateCv } from '../api/jobs'

// Global cache to escape LLM on re-open (session + job)
const _cache = globalThis.__prepareCache || (globalThis.__prepareCache = new Map())

export default function PrepareApplication({ sessionId, job, onClose }) {
  const cacheKey = `${sessionId}_${job.id}`
  const cached = _cache.get(cacheKey)

  const [phase, setPhase] = useState(cached ? 'preview' : 'analyzing')
  const [analysis, setAnalysis] = useState(cached?.analysis || null)
  const [pdfUrl, setPdfUrl] = useState(cached?.pdfUrl || null)
  const [showPdf, setShowPdf] = useState(false)
  const [error, setError] = useState(null)

  const runPrepare = async (force = false) => {
    if (!force && cached) return
    setPhase('analyzing')
    setError(null)
    setShowPdf(false)
    try {
      const res = await prepareApplication({ sessionId, job, force })
      if (res.error) throw new Error(res.error)
      const a = res.analysis
      setAnalysis(a)
      // Auto generate CV for preview (no extra click)
      setPhase('generating')
      const blob = await generateCv({ sessionId, job, analysis: a })
      const url = URL.createObjectURL(blob)
      // revoke old if exists
      if (pdfUrl) URL.revokeObjectURL(pdfUrl)
      setPdfUrl(url)
      _cache.set(cacheKey, { analysis: a, pdfUrl: url })
      setPhase('preview')
    } catch (e) {
      setError(e.response?.data?.error || e.message || 'Failed')
      setPhase('idle')
    }
  }

  useEffect(() => {
    if (!cached) runPrepare(false)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const rerun = () => {
    _cache.delete(cacheKey)
    if (pdfUrl) URL.revokeObjectURL(pdfUrl)
    setPdfUrl(null)
    setAnalysis(null)
    runPrepare(true)
  }

  return (
    <div className="prepare-overlay" onClick={onClose}>
      <div className="prepare-modal" onClick={e => e.stopPropagation()}>
        <div className="prepare-header">
          <h3>Application — {job.title}</h3>
          <p className="muted">{job.company} · {job.location}</p>
        </div>

        {phase === 'analyzing' && (
          <div className="search-progress" style={{ margin: '1rem 0' }}>
            <div className="progress-header"><span className="spinner" /> Preparing your application…</div>
            <div className="progress-steps">
              <div className="progress-step"><Check size={14} color="#10b981" /> Job analyzed</div>
              <div className="progress-step"><Check size={14} color="#10b981" /> Resume matched</div>
              <div className="progress-step active"><span className="spinner-small" /> Tailoring CV</div>
            </div>
          </div>
        )}

        {phase === 'generating' && (
          <div className="search-progress" style={{ margin: '1rem 0' }}><div className="progress-header"><span className="spinner" /> Generating preview CV…</div></div>
        )}

        {error && <div className="empty-state error" style={{ padding: '.8rem' }}><AlertTriangle size={16} /> {error}</div>}

        {phase === 'preview' && analysis && (
          <>
            <div className="analysis-grid" style={{ marginTop: '.8rem' }}>
              <div className="analysis-card">
                <h4><Briefcase size={13} /> Relevant Skills</h4>
                {analysis.relevant_skills?.length ? analysis.relevant_skills.map(s => <span key={s} className="match-chip ok">✓ {s}</span>) : <span className="muted">No overlap</span>}
              </div>
              <div className="analysis-card">
                <h4><Award size={13} /> Relevant Projects</h4>
                {analysis.relevant_projects?.length ? analysis.relevant_projects.map(p => <span key={p} className="match-chip ok">✓ {p}</span>) : <span className="muted">—</span>}
              </div>
              <div className="analysis-card">
                <h4><Sparkles size={13} /> Summary</h4>
                <p style={{ fontSize: '.82rem', color: '#334155', fontStyle: 'italic' }}>{analysis.summary}</p>
              </div>
            </div>

            <div style={{ marginTop: '.9rem', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '.9rem', textAlign: 'center' }}>
              <p style={{ fontSize: '.85rem', fontWeight: 600, marginBottom: '.6rem' }}>Preview CV ready</p>
              {!showPdf ? (
                <button className="search-btn" style={{ width: '100%', justifyContent: 'center' }} onClick={() => setShowPdf(true)}><Eye size={14} /> Show CV</button>
              ) : (
                <div>
                  <iframe src={pdfUrl} title="CV Preview" style={{ width: '100%', height: '480px', border: '1px solid #e2e8f0', borderRadius: '12px' }} />
                  <div style={{ display: 'flex', gap: '.6rem', marginTop: '.7rem' }}>
                    <a href={pdfUrl} download={`CV_${job.title.replace(/\s+/g, '_')}.pdf`} className="search-btn" style={{ flex: 1, justifyContent: 'center', textDecoration: 'none' }}><Download size={14} /> Download PDF</a>
                    <button className="job-btn ghost" onClick={() => setShowPdf(false)}>Hide</button>
                  </div>
                </div>
              )}
              <button className="job-btn ghost" style={{ marginTop: '.6rem', width: '100%', justifyContent: 'center' }} onClick={rerun}><RefreshCw size={13} /> Rerun (new LLM call)</button>
              <p className="muted" style={{ fontSize: '.7rem', marginTop: '.4rem' }}>Rerun escapes cache and calls LLM again. Otherwise preview is cached, no LLM.</p>
            </div>
          </>
        )}

        {phase === 'idle' && (
          <div style={{ padding: '1rem 0' }}>
            <button className="search-btn" style={{ width: '100%', justifyContent: 'center' }} onClick={() => runPrepare(true)}>Prepare Application</button>
          </div>
        )}

        <button className="details-close" style={{ position: 'absolute', top: '.6rem', right: '.6rem' }} onClick={onClose}><span style={{ fontSize: '1.1rem' }}>×</span></button>
      </div>
    </div>
  )
}
