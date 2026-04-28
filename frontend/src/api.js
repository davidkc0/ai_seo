// In dev: Vite proxies /api -> http://localhost:8000 (see vite.config.js).
// In prod on Vercel: set VITE_API_URL=https://<railway-backend>.up.railway.app
const BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL.replace(/\/$/, '')}/api`
  : '/api'

function getToken() {
  return localStorage.getItem('token')
}

async function request(path, options = {}) {
  const token = getToken()
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  }
  const res = await fetch(`${BASE}${path}`, { ...options, headers })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(err.detail || 'Request failed')
  }
  return res.json()
}

export const api = {
  // Auth
  register: (email, password, turnstileToken) =>
    request('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, turnstile_token: turnstileToken || null }),
    }),

  forgotPassword: (email) =>
    request('/auth/forgot-password', { method: 'POST', body: JSON.stringify({ email }) }),

  resetPassword: (token, password) =>
    request('/auth/reset-password', { method: 'POST', body: JSON.stringify({ token, password }) }),

  verifyEmail: (token) =>
    request('/auth/verify-email', { method: 'POST', body: JSON.stringify({ token }) }),

  resendVerification: () =>
    request('/auth/resend-verification', { method: 'POST' }),

  login: (email, password) => {
    const form = new URLSearchParams()
    form.append('username', email)
    form.append('password', password)
    return fetch(`${BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: form,
    }).then(async r => {
      if (!r.ok) {
        const e = await r.json().catch(() => ({ detail: 'Login failed' }))
        throw new Error(e.detail)
      }
      return r.json()
    })
  },

  me: () => request('/auth/me'),

  // Products
  getProducts: () => request('/products/'),
  createProduct: (data) => request('/products/', { method: 'POST', body: JSON.stringify(data) }),
  updateProduct: (id, data) => request(`/products/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteProduct: (id) => request(`/products/${id}`, { method: 'DELETE' }),
  scanProduct: (id) => request(`/products/${id}/scan`, { method: 'POST' }),
  getResults: (id, limit = 50) => request(`/products/${id}/results?limit=${limit}`),
  getSummary: (id) => request(`/products/${id}/summary`),
  getRecommendations: (id) => request(`/products/${id}/recommendations`),
  getAIOverview: (id) => request(`/products/${id}/ai-overview`),
  getScanHistory: (id) => request(`/products/${id}/scan-history`),

  // Billing
  getPlans: () => request('/billing/plans'),
  createCheckout: (plan) => request(`/billing/create-checkout?plan=${plan}`, { method: 'POST' }),
  createPortal: () => request('/billing/portal', { method: 'POST' }),

  // Settings
  getNotifications: () => request('/settings/notifications'),
  updateNotifications: (data) => request('/settings/notifications', { method: 'PUT', body: JSON.stringify(data) }),

  // Bot Analytics
  getBotConnections: () => request('/bot-analytics/connections'),
  getBotZones: (apiToken) => request(`/bot-analytics/zones?api_token=${encodeURIComponent(apiToken)}`),
  connectCloudflare: (data) => request('/bot-analytics/connect', { method: 'POST', body: JSON.stringify(data) }),
  getVercelProjects: (apiToken) => request(`/bot-analytics/vercel-projects?api_token=${encodeURIComponent(apiToken)}`),
  connectVercel: (data) => request('/bot-analytics/connect-vercel', { method: 'POST', body: JSON.stringify(data) }),
  disconnectCdn: (id) => request(`/bot-analytics/connections/${id}`, { method: 'DELETE' }),
  syncBotTraffic: (id, days = 7) => request(`/bot-analytics/sync/${id}`, { method: 'POST', body: JSON.stringify({ days }) }),
  getBotSummary: (days = 30) => request(`/bot-analytics/summary?days=${days}`),
}
