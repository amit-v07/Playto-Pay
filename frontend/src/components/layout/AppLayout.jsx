import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import {
  Zap, LayoutDashboard, ArrowUpRight, BookOpen,
  LogOut, Settings, ChevronRight, User
} from 'lucide-react'
import { formatInr } from '../../utils/format'

const NAV = [
  { to: '/dashboard',      icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/payouts',        icon: ArrowUpRight,    label: 'Payouts' },
  { to: '/ledger',         icon: BookOpen,        label: 'Ledger' },
]

export default function AppLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const balance = user?.balance_paise ?? 0

  return (
    <div className="flex h-screen overflow-hidden">
      {/* ── Sidebar ─────────────────────────────────────────────────── */}
      <aside className="w-60 shrink-0 flex flex-col bg-surface-800 border-r border-surface-600">
        {/* Logo */}
        <div className="px-5 py-5 border-b border-surface-600">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 bg-brand-600 rounded-lg shadow-lg shadow-brand-900/50">
              <Zap size={16} className="text-white" />
            </div>
            <div>
              <p className="text-sm font-bold text-white">Platopay</p>
              <p className="text-[10px] text-slate-500 leading-none">Payout Engine</p>
            </div>
          </div>
        </div>

        {/* Balance card */}
        <div className="mx-3 my-3 p-3.5 bg-gradient-to-br from-brand-700/40 to-brand-900/60
                        border border-brand-500/20 rounded-xl">
          <p className="text-[10px] text-brand-300 font-semibold uppercase tracking-widest mb-1">
            Available Balance
          </p>
          <p className="money text-lg text-white">{formatInr(balance)}</p>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-2 space-y-0.5">
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium
                 transition-all duration-150 group
                 ${isActive
                   ? 'bg-brand-600/20 text-brand-300 border border-brand-500/20'
                   : 'text-slate-400 hover:text-slate-200 hover:bg-surface-700'
                 }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon size={16} className={isActive ? 'text-brand-400' : ''} />
                  {label}
                  {isActive && <ChevronRight size={13} className="ml-auto text-brand-500" />}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* User section */}
        <div className="px-3 pb-4 border-t border-surface-600 pt-3 space-y-0.5">
          <div className="flex items-center gap-2.5 px-3 py-2 mb-1">
            <div className="w-7 h-7 rounded-full bg-brand-700 flex items-center justify-center shrink-0">
              <User size={13} className="text-brand-200" />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-semibold text-slate-200 truncate">
                {user?.business_name}
              </p>
              <p className="text-[10px] text-slate-500 truncate">
                {user?.user?.username}
              </p>
            </div>
          </div>

          <button
            onClick={handleLogout}
            id="btn-logout"
            className="btn-ghost w-full justify-start text-xs gap-2.5 py-2"
          >
            <LogOut size={14} />
            Sign Out
          </button>
        </div>
      </aside>

      {/* ── Main content ─────────────────────────────────────────────── */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
