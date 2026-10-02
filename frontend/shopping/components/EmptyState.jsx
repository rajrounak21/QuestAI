import { AlertTriangle, MessageCircle, SearchX } from 'lucide-react';

export default function EmptyState({ error, followUp }) {
  if (error) {
    return (
      <div className="empty-state error premium">
        <div className="empty-icon"><AlertTriangle size={28} color="#dc2626" /></div>
        <h3>Something went wrong</h3>
        <p>{error}</p>
      </div>
    );
  }
  if (followUp) {
    return (
      <div className="empty-state followup premium">
        <div className="empty-icon"><MessageCircle size={28} color="#2563eb" /></div>
        <h3>Need more info</h3>
        <p>{followUp}</p>
      </div>
    );
  }
  return (
    <div className="empty-state premium">
      <div className="empty-icon"><SearchX size={28} color="#64748b" /></div>
      <h3>No products found</h3>
      <p>Try another search like <strong>iPhone 15</strong> or <strong>Nike shoes</strong></p>
    </div>
  );
}
