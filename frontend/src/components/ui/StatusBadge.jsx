/**
 * Status badge for Payout status or LedgerEntry type.
 */
export function StatusBadge({ status }) {
  const map = {
    PENDING:    { cls: 'badge-pending',    dot: 'bg-amber-400',   label: 'Pending' },
    PROCESSING: { cls: 'badge-processing', dot: 'bg-blue-400 animate-pulse',    label: 'Processing' },
    COMPLETED:  { cls: 'badge-completed',  dot: 'bg-emerald-400', label: 'Completed' },
    FAILED:     { cls: 'badge-failed',     dot: 'bg-red-400',     label: 'Failed' },
    CREDIT:     { cls: 'badge-credit',     dot: 'bg-emerald-400', label: 'Credit' },
    DEBIT:      { cls: 'badge-debit',      dot: 'bg-orange-400',  label: 'Debit' },
  }

  const cfg = map[status?.toUpperCase()] ?? {
    cls: 'badge bg-slate-700 text-slate-400',
    dot: 'bg-slate-400',
    label: status ?? 'Unknown',
  }

  return (
    <span className={cfg.cls}>
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot} shrink-0`} />
      {cfg.label}
    </span>
  )
}
