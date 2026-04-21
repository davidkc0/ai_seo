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
  register: (email, password) =>
    request('/auth/register', { method: 'POST', body: JSON.stringify({ email, password }) }),

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

  // Billing
  getPlans: () => request('/billing/plans'),
  createCheckout: (plan) => request(`/billing/create-checkout?plan=${plan}`, { method: 'POST' }),
  createPortal: () => request('/billing/portal', { method: 'POST' }),

  // Settings
  getNotifications: () => request('/settings/notifications'),
  updateNotifications: (data) => request('/settings/notifications', { method: 'PUT', body: JSON.stringify(data) }),
}
