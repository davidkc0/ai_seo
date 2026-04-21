import React, { useState } from 'react'
import { api } from '../api'
import './ProductModal.css'

const PLAN_LIMITS = {
  free: { keywords: 3, label: '3 keywords (free)' },
  starter: { keywords: 5, label: '5 keywords (Starter)' },
  growth: { keywords: 20, label: '20 keywords (Growth)' },
}

export default function ProductModal({ onClose, onCreated, plan = 'free' }) {
  const [form, setForm] = useState({
    name: '',
    category: '',
    use_case: '',
    keywords: '',
    competitors: '',
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const limits = PLAN_LIMITS[plan] || PLAN_LIMITS.free

  const submit = async (e) => {
    e.preventDefault()
    setError('')

    const keywords = form.keywords.split(',').map(k => k.trim()).filter(Boolean)
    const competitors = form.competitors.split(',').map(c => c.trim()).filter(Boolean)

    if (keywords.length > limits.keywords) {
      setError(`Your plan allows max ${limits.keywords} keywords`)
      return
    }

    setLoading(true)
    try {
      const product = await api.createProduct({
        name: form.name,
        category: form.category,
        use_case: form.use_case || undefined,
        keywords,
        competitors,
      })
      onCreated(product)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Add product to track</h2>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        {error && <div className="error-msg">{error}</div>}

        <form onSubmit={submit}>
          <div className="form-group">
            <label>Product name *</label>
            <input
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              placeholder="e.g. Acme CRM"
              required
              autoFocus
            />
          </div>

          <div className="form-group">
            <label>Category *</label>
            <input
              value={form.category}
              onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
              placeholder="e.g. CRM, project management, email marketing"
              required
            />
            <div className="field-hint">This is what we'll ask AI about: "Best [category] tools"</div>
          </div>

          <div className="form-group">
            <label>Use case (optional)</label>
            <input
              value={form.use_case}
              onChange={e => setForm(f => ({ ...f, use_case: e.target.value }))}
              placeholder="e.g. small business sales teams, remote teams"
            />
          </div>

          <div className="form-group">
            <label>Keywords ({limits.label})</label>
            <input
              value={form.keywords}
              onChange={e => setForm(f => ({ ...f, keywords: e.target.value }))}
              placeholder="e.g. pipeline tracking, deal management, sales automation"
            />
            <div className="field-hint">Comma-separated. We'll ask "best [category] tools for [keyword]"</div>
          </div>

          <div className="form-group">
            <label>Competitors (optional)</label>
            <input
              value={form.competitors}
              onChange={e => setForm(f => ({ ...f, competitors: e.target.value }))}
              placeholder="e.g. Salesforce, HubSpot, Pipedrive"
            />
            <div className="field-hint">Comma-separated. We'll track who else AI mentions.</div>
          </div>

          <div className="modal-actions">
            <button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? 'Adding...' : 'Add product →'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
