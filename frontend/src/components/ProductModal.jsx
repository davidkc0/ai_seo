import React, { useState, useRef } from 'react'
import { api } from '../api'
import { X } from 'lucide-react'
import './ProductModal.css'

const PLAN_LIMITS = {
  free: { keywords: 3, label: 'Free' },
  starter: { keywords: 5, label: 'Starter' },
  growth: { keywords: 20, label: 'Growth' },
}

export default function ProductModal({ onClose, onCreated, onUpdated, plan = 'free', product = null }) {
  const isEdit = !!product
  const limits = PLAN_LIMITS[plan] || PLAN_LIMITS.free

  const [form, setForm] = useState({
    name: product?.name || '',
    category: product?.category || '',
    use_case: product?.use_case || '',
  })
  const [keywords, setKeywords] = useState(product?.keywords || [])
  const [competitors, setCompetitors] = useState(product?.competitors || [])
  const [kwInput, setKwInput] = useState('')
  const [compInput, setCompInput] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const kwRef = useRef(null)
  const compRef = useRef(null)

  const addKeyword = (raw) => {
    const val = raw.trim()
    if (!val) return
    if (keywords.includes(val)) return
    if (keywords.length >= limits.keywords) {
      setError(`Your ${limits.label} plan allows max ${limits.keywords} keywords. Upgrade for more.`)
      return
    }
    setError('')
    setKeywords(prev => [...prev, val])
  }

  const removeKeyword = (idx) => {
    setKeywords(prev => prev.filter((_, i) => i !== idx))
    setError('')
  }

  const addCompetitor = (raw) => {
    const val = raw.trim()
    if (!val || competitors.includes(val)) return
    setCompetitors(prev => [...prev, val])
  }

  const removeCompetitor = (idx) => {
    setCompetitors(prev => prev.filter((_, i) => i !== idx))
  }

  const handlePillInput = (e, inputVal, setInputVal, addFn) => {
    const { key, target } = e
    if (key === 'Enter') {
      e.preventDefault()
      const parts = inputVal.split(',').map(s => s.trim()).filter(Boolean)
      parts.forEach(addFn)
      setInputVal('')
    } else if (key === ',') {
      e.preventDefault()
      addFn(inputVal)
      setInputVal('')
    } else if (key === 'Backspace' && !inputVal) {
      // handled per-field
    }
  }

  const submit = async (e) => {
    e.preventDefault()
    setError('')

    if (keywords.length > limits.keywords) {
      setError(`Your plan allows max ${limits.keywords} keywords`)
      return
    }

    const payload = {
      name: form.name,
      category: form.category,
      use_case: form.use_case || undefined,
      keywords,
      competitors,
    }

    setLoading(true)
    try {
      if (isEdit) {
        await api.updateProduct(product.id, payload)
        onUpdated?.({ ...product, ...payload })
      } else {
        const created = await api.createProduct(payload)
        onCreated?.(created)
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const atLimit = keywords.length >= limits.keywords

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{isEdit ? 'Edit product' : 'Add product to track'}</h2>
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
              autoFocus={!isEdit}
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

          {/* Keywords — pill input */}
          <div className="form-group">
            <label>
              Keywords
              <span className={`pill-counter ${atLimit ? 'at-limit' : ''}`}>
                {keywords.length}/{limits.keywords}
              </span>
            </label>
            <div className={`pill-input-wrapper ${atLimit ? 'at-limit' : ''}`} onClick={() => kwRef.current?.focus()}>
              {keywords.map((kw, i) => (
                <span key={i} className="pill">
                  {kw}
                  <button type="button" className="pill-x" onClick={(e) => { e.stopPropagation(); removeKeyword(i) }}>
                    <X size={10} />
                  </button>
                </span>
              ))}
              {!atLimit && (
                <input
                  ref={kwRef}
                  className="pill-text-input"
                  value={kwInput}
                  onChange={e => setKwInput(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Backspace' && !kwInput && keywords.length > 0) {
                      removeKeyword(keywords.length - 1)
                    }
                    handlePillInput(e, kwInput, setKwInput, addKeyword)
                  }}
                  onBlur={() => { if (kwInput.trim()) { addKeyword(kwInput); setKwInput('') } }}
                  placeholder={keywords.length === 0 ? 'Type a keyword, press comma or enter' : ''}
                />
              )}
            </div>
            <div className="field-hint">
              {atLimit
                ? `Limit reached — upgrade for more keywords`
                : `Press comma or enter to add. We'll ask "best [category] tools for [keyword]"`}
            </div>
          </div>

          {/* Competitors — pill input (no limit) */}
          <div className="form-group">
            <label>Competitors (optional)</label>
            <div className="pill-input-wrapper" onClick={() => compRef.current?.focus()}>
              {competitors.map((c, i) => (
                <span key={i} className="pill pill-neutral">
                  {c}
                  <button type="button" className="pill-x" onClick={(e) => { e.stopPropagation(); removeCompetitor(i) }}>
                    <X size={10} />
                  </button>
                </span>
              ))}
              <input
                ref={compRef}
                className="pill-text-input"
                value={compInput}
                onChange={e => setCompInput(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Backspace' && !compInput && competitors.length > 0) {
                    removeCompetitor(competitors.length - 1)
                  }
                  handlePillInput(e, compInput, setCompInput, addCompetitor)
                }}
                onBlur={() => { if (compInput.trim()) { addCompetitor(compInput); setCompInput('') } }}
                placeholder={competitors.length === 0 ? 'Type a competitor, press comma or enter' : ''}
              />
            </div>
            <div className="field-hint">We'll track who else AI mentions alongside you.</div>
          </div>

          <div className="modal-actions">
            <button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? (isEdit ? 'Saving...' : 'Adding...') : (isEdit ? 'Save changes' : 'Add product →')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
