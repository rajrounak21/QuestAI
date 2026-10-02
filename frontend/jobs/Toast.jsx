import { useEffect, useState } from 'react'
import { CheckCircle, AlertCircle, X } from 'lucide-react'

let pushFn = null
export function pushToast(msg, type = 'success') {
  if (pushFn) pushFn(msg, type)
}

export default function ToastContainer() {
  const [toasts, setToasts] = useState([])

  useEffect(() => {
    pushFn = (msg, type = 'success') => {
      const id = Date.now() + Math.random()
      setToasts(t => [...t, { id, msg, type }])
      setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 3200)
    }
    return () => { pushFn = null }
  }, [])

  return (
    <div className="toast-stack">
      {toasts.map(t => (
        <div key={t.id} className={`toast toast-${t.type}`}>
          {t.type === 'success' ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
          <span>{t.msg}</span>
          <button className="toast-x" onClick={() => setToasts(v => v.filter(x => x.id !== t.id))}><X size={14} /></button>
        </div>
      ))}
    </div>
  )
}
