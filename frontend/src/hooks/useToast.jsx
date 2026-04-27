import { useState, useCallback } from 'react'
import { ToastContainer } from '../components/ui/Toast'

let _id = 0

export function useToast() {
  const [toasts, setToasts] = useState([])

  const addToast = useCallback((type, message, duration = 4000) => {
    const id = ++_id
    setToasts((prev) => [...prev, { id, type, message, duration }])
    return id
  }, [])

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const toast = {
    success: (msg, dur) => addToast('success', msg, dur),
    error:   (msg, dur) => addToast('error',   msg, dur),
    warning: (msg, dur) => addToast('warning', msg, dur),
    info:    (msg, dur) => addToast('info',    msg, dur),
  }

  const ToastPortal = () => (
    <ToastContainer toasts={toasts} removeToast={removeToast} />
  )

  return { toast, ToastPortal }
}
