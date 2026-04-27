import { AlertTriangle, CheckCircle, Info, XCircle, X } from 'lucide-react'
import { useEffect } from 'react'

const ICONS = {
  success: <CheckCircle size={18} className="text-emerald-400 shrink-0" />,
  error:   <XCircle     size={18} className="text-red-400 shrink-0" />,
  warning: <AlertTriangle size={18} className="text-amber-400 shrink-0" />,
  info:    <Info        size={18} className="text-blue-400 shrink-0" />,
}

const STYLES = {
  success: 'bg-emerald-500/10 border-emerald-500/25 text-emerald-300',
  error:   'bg-red-500/10 border-red-500/25 text-red-300',
  warning: 'bg-amber-500/10 border-amber-500/25 text-amber-300',
  info:    'bg-blue-500/10 border-blue-500/25 text-blue-300',
}

/**
 * Toast notification. Auto-dismisses after `duration` ms (0 = never).
 */
export function Toast({ type = 'info', message, onClose, duration = 4000 }) {
  useEffect(() => {
    if (!duration) return
    const t = setTimeout(onClose, duration)
    return () => clearTimeout(t)
  }, [duration, onClose])

  return (
    <div
      className={`flex items-start gap-3 px-4 py-3 rounded-xl border text-sm
                  animate-slide-up shadow-xl ${STYLES[type]}`}
      role="alert"
    >
      {ICONS[type]}
      <p className="flex-1 leading-relaxed">{message}</p>
      <button
        onClick={onClose}
        className="opacity-60 hover:opacity-100 transition-opacity mt-0.5 shrink-0"
        aria-label="Dismiss"
      >
        <X size={14} />
      </button>
    </div>
  )
}

/**
 * Toast container — renders toasts at the bottom-right.
 */
export function ToastContainer({ toasts, removeToast }) {
  return (
    <div
      aria-live="polite"
      className="fixed bottom-6 right-6 z-50 flex flex-col gap-3 w-96 max-w-[calc(100vw-3rem)]"
    >
      {toasts.map((t) => (
        <Toast key={t.id} {...t} onClose={() => removeToast(t.id)} />
      ))}
    </div>
  )
}
