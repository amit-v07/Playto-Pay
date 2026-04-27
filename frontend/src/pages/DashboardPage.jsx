import { useEffect, useState, useCallback } from 'react'
import { useAuth } from '../context/AuthContext'
import { getBalance, listPayouts, getTransactions, simulateCredit } from '../api/services'
import { formatInr, formatDate, generateUUID } from '../utils/format'
import { StatusBadge } from '../components/ui/StatusBadge'
import Spinner from '../components/ui/Spinner'
import { useToast } from '../hooks/useToast'
import {
  TrendingUp, TrendingDown, Clock, CheckCircle,
  XCircle, Plus, RefreshCw, Zap, ArrowUpRight
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { createPayout } from '../api/services'

/* ── Stat card ─────────────────────────────────────────────────────────────── */
function StatCard({ label, value, sub, icon: Icon, color, loading }) {
  const colorMap = {
    brand:   'from-brand-600/20 to-brand-900/10 border-brand-500/20 text-brand-400',
    emerald: 'from-emerald-600/20 to-emerald-900/10 border-emerald-500/20 text-emerald-400',
    amber:   'from-amber-600/20 to-amber-900/10 border-amber-500/20 text-amber-400',
    red:     'from-red-600/20 to-red-900/10 border-red-500/20 text-red-400',
    blue:    'from-blue-600/20 to-blue-900/10 border-blue-500/20 text-blue-400',
  }[color] || ''

  return (
    <div className={`card bg-gradient-to-br ${colorMap} p-5`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs text-slate-400 font-semibold uppercase tracking-wider mb-1.5">{label}</p>
          {loading
            ? <div className="skeleton h-7 w-32 mb-1" />
            : <p className="money text-2xl text-white">{value}</p>
          }
          {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
        </div>
        <div className={`p-2.5 rounded-xl bg-current/10`}>
          <Icon size={18} className="text-current" />
        </div>
      </div>
    </div>
  )
}

/* ── Quick Payout modal ─────────────────────────────────────────────────────── */
function QuickPayoutModal({ onClose, onSuccess, toast }) {
  const [amount, setAmount] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    const paise = Math.round(parseFloat(amount) * 100)
    if (!paise || paise < 100) {
      setError('Minimum withdrawal is ₹1.00')
      return
    }
    setLoading(true)
    setError('')
    try {
      await createPayout(paise, generateUUID())
      toast.success('Payout queued successfully!')
      onSuccess()
      onClose()
    } catch (err) {
      const data = err.response?.data
      if (err.response?.status === 402) {
        setError(`Insufficient balance. Available: ${formatInr(data?.balance_paise ?? 0)}`)
      } else {
        setError(data?.error || 'Failed to create payout.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="card w-full max-w-sm p-6 animate-slide-up shadow-2xl">
        <h2 className="text-lg font-bold text-white mb-1">Request Payout</h2>
        <p className="text-sm text-slate-400 mb-5">Funds will be settled to your bank account.</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="modal-amount" className="label">Amount (₹)</label>
            <div className="relative">
              <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 text-sm font-mono">₹</span>
              <input
                id="modal-amount"
                type="number"
                min="1"
                step="0.01"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="0.00"
                className="input pl-8 font-mono"
                required
                autoFocus
              />
            </div>
          </div>

          {error && (
            <p className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-xl px-3 py-2">
              {error}
            </p>
          )}

          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose} className="btn-secondary flex-1 justify-center">
              Cancel
            </button>
            <button type="submit" disabled={loading} id="btn-submit-payout" className="btn-primary flex-1 justify-center">
              {loading ? <Spinner size={16} /> : 'Submit'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

/* ── Simulate Credit modal ──────────────────────────────────────────────────── */
function SimulateCreditModal({ onClose, onSuccess, toast }) {
  const [amount, setAmount] = useState('')
  const [desc, setDesc]     = useState('Payment received')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    const paise = Math.round(parseFloat(amount) * 100)
    if (!paise || paise <= 0) return
    setLoading(true)
    try {
      await simulateCredit(paise, desc)
      toast.success(`Credited ${formatInr(paise)} to your account!`)
      onSuccess()
      onClose()
    } catch {
      toast.error('Failed to simulate credit.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="card w-full max-w-sm p-6 animate-slide-up shadow-2xl">
        <h2 className="text-lg font-bold text-white mb-1">Simulate Credit</h2>
        <p className="text-sm text-slate-400 mb-5">Add test funds to your merchant account.</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="credit-amount" className="label">Amount (₹)</label>
            <div className="relative">
              <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 text-sm font-mono">₹</span>
              <input id="credit-amount" type="number" min="1" step="0.01"
                value={amount} onChange={(e) => setAmount(e.target.value)}
                placeholder="0.00" className="input pl-8 font-mono" required autoFocus />
            </div>
          </div>
          <div>
            <label htmlFor="credit-desc" className="label">Description</label>
            <input id="credit-desc" type="text" value={desc}
              onChange={(e) => setDesc(e.target.value)} className="input" />
          </div>

          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose} className="btn-secondary flex-1 justify-center">Cancel</button>
            <button type="submit" disabled={loading} id="btn-submit-credit" className="btn-success flex-1 justify-center">
              {loading ? <Spinner size={16} /> : 'Add Credit'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

/* ── Dashboard page ──────────────────────────────────────────────────────────── */
export default function DashboardPage() {
  const { user, refreshUser } = useAuth()
  const { toast, ToastPortal } = useToast()

  const [balance, setBalance]   = useState(null)
  const [payouts, setPayouts]   = useState([])
  const [txns, setTxns]         = useState([])
  const [loading, setLoading]   = useState(true)
  const [showPayout, setShowPayout]   = useState(false)
  const [showCredit, setShowCredit]   = useState(false)
  const [refreshing, setRefreshing]   = useState(false)

  const loadData = useCallback(async () => {
    try {
      const [balRes, payRes, txRes] = await Promise.all([
        getBalance(),
        listPayouts({ page_size: 5 }),
        getTransactions({ page_size: 5 }),
      ])
      setBalance(balRes.data)
      setPayouts(payRes.data.results ?? payRes.data)
      setTxns(txRes.data.results ?? txRes.data)
    } catch {
      toast.error('Failed to load dashboard data.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const refresh = async () => {
    setRefreshing(true)
    await Promise.all([loadData(), refreshUser()])
    setRefreshing(false)
  }

  const statusCounts = payouts.reduce((acc, p) => {
    acc[p.status] = (acc[p.status] || 0) + 1
    return acc
  }, {})

  return (
    <div className="p-6 max-w-6xl mx-auto animate-fade-in">
      <ToastPortal />
      {showPayout && (
        <QuickPayoutModal
          onClose={() => setShowPayout(false)}
          onSuccess={refresh}
          toast={toast}
        />
      )}
      {showCredit && (
        <SimulateCreditModal
          onClose={() => setShowCredit(false)}
          onSuccess={refresh}
          toast={toast}
        />
      )}

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">
            Good {new Date().getHours() < 12 ? 'morning' : new Date().getHours() < 17 ? 'afternoon' : 'evening'},{' '}
            <span className="text-brand-400">{user?.business_name}</span> 👋
          </h1>
          <p className="text-slate-400 text-sm mt-0.5">Here's your financial overview</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={refresh}
            disabled={refreshing}
            className="btn-ghost"
            title="Refresh data"
          >
            <RefreshCw size={15} className={refreshing ? 'animate-spin' : ''} />
          </button>
          <button onClick={() => setShowCredit(true)} id="btn-simulate-credit" className="btn-secondary">
            <Plus size={15} />
            Simulate Credit
          </button>
          <button onClick={() => setShowPayout(true)} id="btn-new-payout" className="btn-primary">
            <ArrowUpRight size={15} />
            New Payout
          </button>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard
          label="Available Balance" icon={Zap} color="brand" loading={loading}
          value={formatInr(balance?.balance_paise ?? 0)}
          sub={`${formatInr(balance?.total_credits_paise ?? 0)} credited total`}
        />
        <StatCard
          label="Total Credits" icon={TrendingUp} color="emerald" loading={loading}
          value={formatInr(balance?.total_credits_paise ?? 0)}
          sub="All-time"
        />
        <StatCard
          label="Total Debits" icon={TrendingDown} color="amber" loading={loading}
          value={formatInr(balance?.total_debits_paise ?? 0)}
          sub="All-time"
        />
        <StatCard
          label="Active Payouts" icon={Clock} color="blue" loading={loading}
          value={`${(statusCounts['PENDING'] || 0) + (statusCounts['PROCESSING'] || 0)}`}
          sub={`${statusCounts['COMPLETED'] || 0} completed`}
        />
      </div>

      {/* Recent sections */}
      <div className="grid lg:grid-cols-2 gap-5">
        {/* Recent payouts */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-white">Recent Payouts</h2>
            <Link to="/payouts" className="text-xs text-brand-400 hover:text-brand-300 font-medium">
              View all →
            </Link>
          </div>

          {loading ? (
            <div className="space-y-3">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="skeleton h-12 w-full" />
              ))}
            </div>
          ) : payouts.length === 0 ? (
            <div className="text-center py-8 text-slate-500">
              <ArrowUpRight size={32} className="mx-auto mb-2 opacity-30" />
              <p className="text-sm">No payouts yet</p>
            </div>
          ) : (
            <div className="space-y-2">
              {payouts.slice(0, 5).map((p) => (
                <div key={p.id} className="flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-surface-700/50 transition-colors">
                  <StatusBadge status={p.status} />
                  <div className="flex-1 min-w-0">
                    <p className="money-sm text-white">{formatInr(p.amount)}</p>
                    <p className="text-[10px] text-slate-500">{formatDate(p.created_at)}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent transactions */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-white">Recent Transactions</h2>
            <Link to="/ledger" className="text-xs text-brand-400 hover:text-brand-300 font-medium">
              View all →
            </Link>
          </div>

          {loading ? (
            <div className="space-y-3">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="skeleton h-12 w-full" />
              ))}
            </div>
          ) : txns.length === 0 ? (
            <div className="text-center py-8 text-slate-500">
              <TrendingUp size={32} className="mx-auto mb-2 opacity-30" />
              <p className="text-sm">No transactions yet</p>
            </div>
          ) : (
            <div className="space-y-2">
              {txns.slice(0, 5).map((t) => (
                <div key={t.id} className="flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-surface-700/50 transition-colors">
                  <StatusBadge status={t.entry_type} />
                  <div className="flex-1 min-w-0">
                    <p className="money-sm text-white">{formatInr(t.amount)}</p>
                    <p className="text-[10px] text-slate-500 truncate">{t.description || '—'}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
