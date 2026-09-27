import { SearchX, MessageCircle, AlertTriangle } from 'lucide-react'

export default function EmptyState({ error, followUp }) {
  if (error) {
    return (
      <div className="empty-state error">
        <AlertTriangle size={28} color="#ef4444" />
        <h3>Something went wrong</h3>
        <p>{error}</p>
      </div>
    )
  }
  if (followUp) {
    return (
      <div className="empty-state follow-up">
        <MessageCircle size={28} color="#4a90d9" />
        <h3>Need a bit more info</h3>
        <p>{followUp}</p>
      </div>
    )
  }
  return (
    <div className="empty-state">
      <SearchX size={28} color="#94a3b8" />
      <h3>No jobs found</h3>
      <p>Try a broader role or different location.</p>
    </div>
  )
}
