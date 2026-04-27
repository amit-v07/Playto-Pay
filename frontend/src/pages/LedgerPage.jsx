import { useEffect, useState, useCallback } from 'react'
import { getBalance, getTransactions, simulateCredit } from '../api/services'
import { formatInr, formatDate } from '../utils/format'
import { StatusBadge } from '../components/ui/StatusBadge'
import Spinner from '../components/ui/Spinner'
import { useToast } from '../hooks/useToast'
import { RefreshCw, TrendingUp, TrendingDown, Filter, Plus } from 'lucide-react'

const TYPES = ['ALL', 'CREDIT', 'DEBIT']

function BalanceHeader({ balance, loading }) {
  if (loading) return <div className="skeleton h-24 w-full rounded-2xl" />

  const b = balance?.balance_paise ?? 0
  const credits = balance?.total_credits_paise ?? 0
  const debits  = balance?.total_debits_paise ?? 0

  return (
    <div className="card bg-gradient-to-r from-brand-900/60 to-surface-800 border-brand-500/20 p-6 flex items-center gap-8">
      <div className="flex-1">
        <p className="text-xs text-brand-300 font-semibold uppercase tracking-widest mb-1">Net Balance</p>
        <p className="money text-4xl text-white">{formatInr(b)}</p>
        <p className="text-xs text-slate-500 mt-1.5">
          Computed live from {(credits + debits) > 0 ? 'all ledger entries' : 'no entries yet'}
        </p>
      </div>
      <div className="flex gap-6 shrink-0">
        <div className="text-right">
          <div className="flex items-center gap-1.5 text-emerald-400 text-xs font-semibold mb-1">
            <TrendingUp size={13} /> Total Credits
          </div>
          <p className="money text-lg text-emerald-300">{formatInr(credits)}</p>
        </div>
        <div className="h-10 w-px bg-surface-600 self-center" />
        <div className="text-right">
          <div className="flex items-center gap-1.5 text-orange-400 text-xs font-semibold mb-1">
            <TrendingDown size={13} /> Total Debits
          </div>
          <p className="money text-lg text-orange-300">{formatInr(debits)}</p>
        </div>
      </div>
    </div>
  )
}

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
      toast.success(`Credited ${formatInr(paise)}!`)
      onSuccess()
      onClose()
    } catch { toast.error('Failed to simulate credit.') }
    finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="card w-full max-w-sm p-6 animate-slide-up shadow-2xl">
        <h2 className="text-lg font-bold text-white mb-4">Simulate Incoming Payment</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="ledger-amount" className="label">Amount (₹)</label>
            <div className="relative">
              <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 text-sm font-mono">₹</span>
              <input id="ledger-amount" type="number" min="0.01" step="0.01"
                value={amount} onChange={(e) => setAmount(e.target.value)}
                className="input pl-8 font-mono" required autoFocus />
            </div>
          </div>
          <div>
            <label htmlFor="ledger-desc" className="label">Description</label>
            <input id="ledger-desc" type="text" value={desc}
              onChange={(e) => setDesc(e.target.value)} className="input" />
          </div>
          <div className="flex gap-3">
            <button type="button" onClick={onClose} className="btn-secondary flex-1 justify-center">Cancel</button>
            <button type="submit" disabled={loading} id="btn-ledger-credit" className="btn-success flex-1 justify-center">
              {loading ? <Spinner size={16} /> : '+ Add Credit'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function LedgerPage() {
  const { toast, ToastPortal } = useToast()
  const [balance, setBalance]     = useState(null)
  const [txns, setTxns]           = useState([])
  const [loading, setLoading]     = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [typeFilter, setTypeFilter] = useState('ALL')
  const [showModal, setShowModal] = useState(false)

  const load = useCallback(async () => {
    try {
      const params = typeFilter !== 'ALL' ? { type: typeFilter } : {}
      const [balRes, txRes] = await Promise.all([
        getBalance(),
        getTransactions(params),
      ])
      setBalance(balRes.data)
      setTxns(txRes.data.results ?? txRes.data)
    } catch { toast.error('Failed to load ledger.') }
    finally { setLoading(false) }
  }, [typeFilter])

  useEffect(() => { setLoading(true); load() }, [load])

  const refresh = async () => {
    setRefreshing(true)
    await load()
    setRefreshing(false)
  }

  return (
    <div className="p-6 max-w-4xl mx-auto animate-fade-in">
      <ToastPortal />
      {showModal && (
        <SimulateCreditModal
          onClose={() => setShowModal(false)}
          onSuccess={refresh}
          toast={toast}
        />
      )}

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Ledger</h1>
          <p className="text-slate-400 text-sm mt-0.5">Immutable, append-only transaction history</p>
        </div>
        <div className="flex gap-2">
          <button onClick={refresh} disabled={refreshing} className="btn-ghost">
            <RefreshCw size={15} className={refreshing ? 'animate-spin' : ''} />
          </button>
          <button onClick={() => setShowModal(true)} id="btn-ledger-new-credit" className="btn-success">
            <Plus size={15} /> Simulate Credit
          </button>
        </div>
      </div>

      {/* Balance header */}
      <div className="mb-5">
        <BalanceHeader balance={balance} loading={loading} />
      </div>

      {/* Filter */}
      <div className="flex items-center gap-2 mb-4">
        <Filter size={13} className="text-slate-500" />
        {TYPES.map((t) => (
          <button
            key={t}
            onClick={() => setTypeFilter(t)}
            className={`px-3 py-1 rounded-full text-xs font-semibold transition-all
              ${typeFilter === t
                ? 'bg-brand-600 text-white'
                : 'bg-surface-700 text-slate-400 hover:text-slate-200 hover:bg-surface-600'
              }`}
          >
            {t === 'ALL' ? 'All' : t.charAt(0) + t.slice(1).toLowerCase()}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-48"><Spinner size={28} /></div>
        ) : txns.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-slate-500">
            <TrendingUp size={36} className="mb-2 opacity-30" />
            <p>No transactions yet</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-600 bg-surface-700/30">
                <th className="px-5 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Type</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Amount</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Description</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Payout</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Date</th>
              </tr>
            </thead>
            <tbody>
              {txns.map((t) => (
                <tr key={t.id} className="table-row-hover border-b border-surface-600 last:border-0">
                  <td className="px-5 py-3.5"><StatusBadge status={t.entry_type} /></td>
                  <td className={`px-5 py-3.5 money-sm font-semibold ${
                    t.entry_type === 'CREDIT' ? 'text-emerald-400' : 'text-orange-400'
                  }`}>
                    {t.entry_type === 'CREDIT' ? '+' : '-'}{formatInr(t.amount)}
                  </td>
                  <td className="px-5 py-3.5 text-slate-300 max-w-xs truncate">
                    {t.description || '—'}
                  </td>
                  <td className="px-5 py-3.5">
                    {t.payout_id
                      ? <span className="font-mono text-xs text-brand-400">{t.payout_id.slice(0, 8)}…</span>
                      : <span className="text-slate-600">—</span>
                    }
                  </td>
                  <td className="px-5 py-3.5 text-xs text-slate-400">{formatDate(t.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <p className="text-center text-xs text-slate-600 mt-4">
        Ledger entries are immutable. No row is ever updated or deleted.
      </p>
    </div>
  )
}
