import api from './client'

// ── Auth ───────────────────────────────────────────────────────────────────────
export const login = (username, password) =>
  api.post('/auth/token/', { username, password })

export const register = (data) =>
  api.post('/merchants/register/', data)

// ── Merchant / Profile ─────────────────────────────────────────────────────────
export const getMe = () => api.get('/merchants/me/')
export const updateMe = (data) => api.patch('/merchants/me/', data)

// ── Ledger ─────────────────────────────────────────────────────────────────────
export const getBalance = () => api.get('/ledger/balance/')
export const getTransactions = (params = {}) =>
  api.get('/ledger/transactions/', { params })
export const simulateCredit = (amount, description) =>
  api.post('/ledger/credit/', { amount, description })

// ── Payouts ────────────────────────────────────────────────────────────────────
export const createPayout = (amount, idempotencyKey) =>
  api.post('/payouts/', { amount }, { headers: { 'Idempotency-Key': idempotencyKey } })

export const listPayouts = (params = {}) =>
  api.get('/payouts/list/', { params })

export const getPayout = (id) => api.get(`/payouts/${id}/`)
