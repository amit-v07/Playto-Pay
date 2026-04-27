import { useEffect, useState, useCallback } from 'react'
import { listPayouts, getPayout, createPayout } from '../api/services'
import { formatInr, formatDate, generateUUID, timeAgo } from '../utils/format'
import { StatusBadge } from '../components/ui/StatusBadge'
import Spinner from '../components/ui/Spinner'
import { useToast } from '../hooks/useToast'
import { ArrowUpRight, RefreshCw, ChevronDown, ChevronUp, Filter, Plus } from 'lucide-react'

const STATUSES = ['ALL', 'PENDING', 'PROCESSING', 'COMPLETED', 'FAILED']

function AuditTimeline({ logs }) {
  if (!logs || logs.length === 0) return null
  return (
    <div className="mt-4 space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Audit Trail</p>
      <div className="relative pl-4">
        <div className="absolute left-0 top-0 bottom-0 w-px bg-surface-500" />
        {logs.map((log) => (
          <div key={log.id} className="relative mb-3 last:mb-0">
            <div className="absolute -left-[13px] top-1.5 w-2 h-2 rounded-full bg-brand-500 border-2 border-surface-800" />
            <div className="bg-surface-700/50 rounded-lg px-3 py-2 ml-2">
              <div className="flex items-center gap-2 text-xs">
                <span className="text-slate-400">
                  {log.old_status
                    ? <><StatusBadge status={log.old_status} /> → <StatusBadge status={log.new_status} /></>
                    : <StatusBadge status={log.new_status} />
                  }
                </span>
                <span className="ml-auto text-slate-500 font-mono">{timeAgo(log.created_at)}</span>
              </div>
              <p className="text-[10px] text-slate-500 mt-1">by {log.actor}</p>
              {log.metadata?.reason && (
                <p className="text-[10px] text-red-400 mt-0.5">Reason: {log.metadata.reason}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function PayoutRow({ payout, onExpand, expanded }) {
  const [detail, setDetail] = useState(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  const toggleExpand = async () => {
    if (expanded) { onExpand(null); return }
    onExpand(payout.id)
    if (!detail) {
      setLoadingDetail(true)
      try {
        const { data } = await getPayout(payout.id)
        setDetail(data)
      } catch { /* ignore */ }
      finally { setLoadingDetail(false) }
    }
  }

  return (
    <>
      <tr
        onClick={toggleExpand}
        className="table-row-hover border-b border-surface-600 last:border-0"
      >
        <td className="px-5 py-3.5">
          <span className="font-mono text-xs text-slate-400">{payout.id.slice(0, 8)}…</span>
        </td>
        <td className="px-5 py-3.5">
          <StatusBadge status={payout.status} />
        </td>
        <td className="px-5 py-3.5 font-mono font-semibold text-white text-sm">
          {formatInr(payout.amount)}
        </td>
        <td className="px-5 py-3.5 text-xs text-slate-400">
          {payout.retry_count > 0 && (
            <span className="mr-2 px-1.5 py-0.5 bg-amber-500/15 text-amber-400 rounded text-[10px]">
              retry #{payout.retry_count}
            </span>
          )}
          {formatDate(payout.created_at)}
        </td>
        <td className="px-5 py-3.5 text-slate-500">
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </td>
      </tr>

      {expanded && (
        <tr className="bg-surface-700/30">
          <td colSpan={5} className="px-6 py-4">
            {loadingDetail
              ? <div className="flex items-center gap-2 text-slate-400 text-sm"><Spinner size={14} /> Loading details…</div>
              : detail
                ? (
                  <div className="grid sm:grid-cols-2 gap-4">
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-slate-400">Payout ID</span>
                        <span className="font-mono text-xs text-slate-300">{detail.id}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Amount</span>
                        <span className="money text-white">{formatInr(detail.amount)}</span>
                      </div>
                      {detail.failure_reason && (
                        <div className="px-3 py-2 bg-red-500/10 border border-red-500/20 rounded-lg">
                          <p className="text-xs text-red-400">{detail.failure_reason}</p>
                        </div>
                      )}
                    </div>
                    <AuditTimeline logs={detail.audit_logs} />
                  </div>
                )
              : null
            }
          </td>
        </tr>
      )}
    </>
  )
}

/* ── New Payout Modal ─────────────────────────────────────────────────────── */
function NewPayoutModal({ onClose, onSuccess, toast }) {
  const [amount, setAmount] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    const paise = Math.round(parseFloat(amount) * 100)
    if (!paise || paise < 100) { setError('Minimum ₹1.00'); return }
    setLoading(true)
    setError('')
    try {
      await createPayout(paise, generateUUID())
      toast.success('Payout queued!')
      onSuccess()
      onClose()
    } catch (err) {
      const data = err.response?.data
      if (err.response?.status === 402) {
        setError(`Insufficient balance. Available: ${formatInr(data?.balance_paise ?? 0)}`)
      } else {
        setError(data?.error || 'Failed.')
      }
    } finally {
      setLoading(false) }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="card w-full max-w-sm p-6 animate-slide-up shadow-2xl">
        <h2 className="text-lg font-bold text-white mb-4">New Payout</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="payout-amount" className="label">Amount (₹)</label>
            <div className="relative">
              <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 text-sm font-mono">₹</span>
              <input id="payout-amount" type="number" min="1" step="0.01"
                value={amount} onChange={(e) => setAmount(e.target.value)}
                placeholder="0.00" className="input pl-8 font-mono" required autoFocus />
            </div>
          </div>
          {error && <p className="text-red-400 text-sm">{error}</p>}
          <div className="flex gap-3">
            <button type="button" onClick={onClose} className="btn-secondary flex-1 justify-center">Cancel</button>
            <button type="submit" disabled={loading} id="btn-payouts-submit" className="btn-primary flex-1 justify-center">
              {loading ? <Spinner size={16} /> : 'Submit'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

/* ── Payouts page ────────────────────────────────────────────────────────────── */
export default function PayoutsPage() {
  const { toast, ToastPortal } = useToast()
  const [payouts, setPayouts]     = useState([])
  const [loading, setLoading]     = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [filter, setFilter]       = useState('ALL')
  const [expandedId, setExpandedId] = useState(null)
  const [showModal, setShowModal] = useState(false)

  const load = useCallback(async () => {
    try {
      const params = filter !== 'ALL' ? { status: filter } : {}
      const { data } = await listPayouts(params)
      setPayouts(data.results ?? data)
    } catch {
      toast.error('Failed to load payouts.')
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => { setLoading(true); load() }, [load])

  const refresh = async () => {
    setRefreshing(true)
    await load()
    setRefreshing(false)
  }

  // Auto-refresh every 5s if any payout is in a non-terminal state
  useEffect(() => {
    const hasActive = payouts.some(
      (p) => p.status === 'PENDING' || p.status === 'PROCESSING'
    )
    if (!hasActive) return
    const id = setInterval(load, 5000)
    return () => clearInterval(id)
  }, [payouts, load])

  return (
    <div className="p-6 max-w-5xl mx-auto animate-fade-in">
      <ToastPortal />
      {showModal && (
        <NewPayoutModal
          onClose={() => setShowModal(false)}
          onSuccess={refresh}
          toast={toast}
        />
      )}

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Payouts</h1>
          <p className="text-slate-400 text-sm mt-0.5">Track all your withdrawal requests</p>
        </div>
        <div className="flex gap-2">
          <button onClick={refresh} disabled={refreshing} className="btn-ghost">
            <RefreshCw size={15} className={refreshing ? 'animate-spin' : ''} />
          </button>
          <button onClick={() => setShowModal(true)} id="btn-payouts-new" className="btn-primary">
            <Plus size={15} /> New Payout
          </button>
        </div>
      </div>

      {/* Status filter */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <Filter size={13} className="text-slate-500" />
        {STATUSES.map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`px-3 py-1 rounded-full text-xs font-semibold transition-all
              ${filter === s
                ? 'bg-brand-600 text-white'
                : 'bg-surface-700 text-slate-400 hover:text-slate-200 hover:bg-surface-600'
              }`}
          >
            {s === 'ALL' ? 'All' : s.charAt(0) + s.slice(1).toLowerCase()}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-48">
            <Spinner size={28} />
          </div>
        ) : payouts.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-slate-500">
            <ArrowUpRight size={36} className="mb-2 opacity-30" />
            <p>No payouts found</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-600 bg-surface-700/30">
                <th className="px-5 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">ID</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Status</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Amount</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Created</th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody>
              {payouts.map((p) => (
                <PayoutRow
                  key={p.id}
                  payout={p}
                  expanded={expandedId === p.id}
                  onExpand={setExpandedId}
                />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
