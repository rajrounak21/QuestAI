import { AlertTriangle, X } from 'lucide-react'

export default function ConfirmModal({ open, title = 'Confirm', message, confirmText = 'Delete', cancelText = 'Cancel', onConfirm, onCancel, loading }) {
  if (!open) return null
  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal-card confirm-modal" onClick={e => e.stopPropagation()}>
        <button className="modal-close" onClick={onCancel}><X size={16} /></button>
        <div className="confirm-icon"><AlertTriangle size={20} color="#ef4444" /></div>
        <h3 className="confirm-title">{title}</h3>
        <p className="confirm-msg">{message}</p>
        <div className="confirm-actions">
          <button className="job-btn primary" onClick={onCancel} disabled={loading}>{cancelText}</button>
          <button className="job-btn danger" onClick={onConfirm} disabled={loading}>{loading ? 'Deleting…' : confirmText}</button>
        </div>
      </div>
    </div>
  )
}
