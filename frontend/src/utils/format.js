/**
 * Format a paise (integer) value to a human-readable INR string.
 * e.g. 1050000 → "₹10,500.00"
 */
export function formatInr(paise) {
  if (paise == null) return '—'
  const rupees = paise / 100
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
  }).format(rupees)
}

/**
 * Generate a cryptographically random UUID v4.
 */
export function generateUUID() {
  return crypto.randomUUID()
}

/**
 * Format an ISO timestamp to a friendly local string.
 */
export function formatDate(iso) {
  if (!iso) return '—'
  return new Intl.DateTimeFormat('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(iso))
}

/**
 * Format a relative time (e.g. "2 minutes ago") from an ISO timestamp.
 */
export function timeAgo(iso) {
  if (!iso) return '—'
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 1)  return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24)  return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

/**
 * Clamp a number between min and max.
 */
export function clamp(val, min, max) {
  return Math.min(Math.max(val, min), max)
}
