import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { register } from '../api/services'
import { Zap, Eye, EyeOff, ArrowRight, Building2, User, Lock, Mail, Globe } from 'lucide-react'
import Spinner from '../components/ui/Spinner'

function Field({ label, id, icon: Icon, type = 'text', ...props }) {
  const [show, setShow] = useState(false)
  const isPassword = type === 'password'
  return (
    <div>
      <label htmlFor={id} className="label">{label}</label>
      <div className="relative">
        {Icon && (
          <Icon size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
        )}
        <input
          id={id}
          type={isPassword && show ? 'text' : type}
          className={`input ${Icon ? 'pl-10' : ''} ${isPassword ? 'pr-10' : ''}`}
          {...props}
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => setShow((s) => !s)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
          >
            {show ? <EyeOff size={15} /> : <Eye size={15} />}
          </button>
        )}
      </div>
    </div>
  )
}

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [tab, setTab]         = useState('login')  // 'login' | 'register'
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')
  const [form, setForm]       = useState({
    username: '', password: '', email: '',
    business_name: '', webhook_url: '',
  })

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const handleLogin = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(form.username, form.password)
      navigate('/dashboard')
    } catch (err) {
      const msg = err.response?.data?.detail || 'Invalid credentials. Please try again.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const handleRegister = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await register({
        username: form.username,
        password: form.password,
        email: form.email,
        business_name: form.business_name,
        webhook_url: form.webhook_url || undefined,
      })
      await login(form.username, form.password)
      navigate('/dashboard')
    } catch (err) {
      const data = err.response?.data
      const msg = data?.username?.[0] || data?.email?.[0] || data?.detail || 'Registration failed.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      {/* Background glow orbs */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-[600px] h-[600px] rounded-full bg-brand-600/10 blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-[500px] h-[500px] rounded-full bg-brand-800/15 blur-3xl" />
      </div>

      <div className="w-full max-w-md animate-fade-in">
        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <div className="p-2.5 bg-brand-600 rounded-xl shadow-lg shadow-brand-900/50">
            <Zap size={22} className="text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight">Platopay</h1>
            <p className="text-xs text-slate-500">Payout Engine</p>
          </div>
        </div>

        {/* Card */}
        <div className="card-glass p-8 shadow-2xl">
          {/* Tabs */}
          <div className="flex bg-surface-900/60 rounded-xl p-1 mb-6">
            {['login', 'register'].map((t) => (
              <button
                key={t}
                onClick={() => { setTab(t); setError('') }}
                className={`flex-1 py-2 rounded-lg text-sm font-semibold transition-all duration-200 ${
                  tab === t
                    ? 'bg-brand-600 text-white shadow-md'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {t === 'login' ? 'Sign In' : 'Register'}
              </button>
            ))}
          </div>

          <form onSubmit={tab === 'login' ? handleLogin : handleRegister} className="space-y-4">
            <Field label="Username" id="username" icon={User}
              value={form.username} onChange={set('username')} required autoComplete="username" />

            <Field label="Password" id="password" icon={Lock} type="password"
              value={form.password} onChange={set('password')} required autoComplete={tab === 'login' ? 'current-password' : 'new-password'} />

            {tab === 'register' && (
              <>
                <Field label="Email" id="email" icon={Mail} type="email"
                  value={form.email} onChange={set('email')} required />
                <Field label="Business Name" id="business_name" icon={Building2}
                  value={form.business_name} onChange={set('business_name')} required />
                <Field label="Webhook URL (optional)" id="webhook_url" icon={Globe}
                  type="url" value={form.webhook_url} onChange={set('webhook_url')}
                  placeholder="https://your-server.com/webhook" />
              </>
            )}

            {error && (
              <div className="px-4 py-3 bg-red-500/10 border border-red-500/25 rounded-xl text-red-300 text-sm animate-slide-up">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              id={tab === 'login' ? 'btn-login' : 'btn-register'}
              className="btn-primary w-full justify-center py-3 mt-2"
            >
              {loading ? <Spinner size={16} /> : (
                <>
                  {tab === 'login' ? 'Sign In' : 'Create Account'}
                  <ArrowRight size={16} />
                </>
              )}
            </button>
          </form>

          {tab === 'login' && (
            <p className="text-center text-xs text-slate-500 mt-5">
              Demo accounts: <code className="text-brand-400 font-mono">alice</code> /{' '}
              <code className="text-brand-400 font-mono">bob</code> — password:{' '}
              <code className="text-brand-400 font-mono">password123</code>
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
