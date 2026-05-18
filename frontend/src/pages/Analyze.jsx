import React, { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, Loader, SearchCheck } from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../AuthContext'
import WebsiteAuditReport from '../components/WebsiteAuditReport'
import illusionLogo from '../assets/illusion_logo.svg'
import { track } from '../analytics'
import './Analyze.css'

const TURNSTILE_SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY || ''

export default function Analyze() {
  const [url, setUrl] = useState('')
  const [audit, setAudit] = useState(null)
  const [publicToken, setPublicToken] = useState('')
  const [turnstileToken, setTurnstileToken] = useState('')
  const [loading, setLoading] = useState(false)
  const [claiming, setClaiming] = useState(false)
  const [error, setError] = useState('')
  const completedRef = useRef(false)
  const pollRef = useRef(null)
  const { user } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (!TURNSTILE_SITE_KEY) return
    window.onAuditTurnstileSuccess = (token) => setTurnstileToken(token)
    const existing = document.querySelector('script[data-turnstile]')
    if (existing) return
    const s = document.createElement('script')
    s.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js'
    s.async = true
    s.defer = true
    s.dataset.turnstile = '1'
    document.body.appendChild(s)
    return () => {
      delete window.onAuditTurnstileSuccess
    }
  }, [])

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  const pollAudit = (id, token) => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const data = await api.getPublicWebsiteAudit(id, token)
        setAudit(data)
        if (data.status === 'completed' || data.status === 'failed') {
          clearInterval(pollRef.current)
          pollRef.current = null
          setLoading(false)
          if (data.status === 'completed' && !completedRef.current) {
            completedRef.current = true
            track.auditCompleted(data.scores?.overall)
          }
        }
      } catch (e) {
        setError(e.message)
        setLoading(false)
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }, 3500)
  }

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    completedRef.current = false
    if (TURNSTILE_SITE_KEY && !turnstileToken) {
      setError('Please complete the captcha to continue.')
      return
    }
    setLoading(true)
    try {
      const start = await api.startPublicWebsiteAudit({ url, turnstile_token: turnstileToken || null })
      track.auditStarted('public')
      setPublicToken(start.public_token)
      const initial = await api.getPublicWebsiteAudit(start.audit_id, start.public_token)
      setAudit(initial)
      pollAudit(start.audit_id, start.public_token)
    } catch (e) {
      setError(e.message)
      setLoading(false)
    }
  }

  const claimAudit = async () => {
    if (!audit || !publicToken) return
    const pending = {
      audit_id: audit.id,
      public_token: publicToken,
      url: audit.normalized_url || url,
    }
    localStorage.setItem('pendingWebsiteAudit', JSON.stringify(pending))

    if (!user) {
      track.signupFromAudit()
      navigate('/register?source=audit')
      return
    }

    setClaiming(true)
    try {
      const existingProducts = await api.getProducts().catch(() => [])
      let productName = ''
      try {
        productName = new URL(audit.normalized_url || url).hostname.replace(/^www\./, '')
      } catch {
        productName = audit.domain || 'My website'
      }
      await api.claimWebsiteAudit(audit.id, {
        public_token: publicToken,
        create_product: existingProducts.length === 0,
        product_name: productName,
        category: 'local service business',
        use_case: 'small business customers',
      })
      localStorage.removeItem('pendingWebsiteAudit')
      track.auditClaimed()
      navigate('/dashboard?tab=audit')
    } catch (e) {
      setError(e.message)
    } finally {
      setClaiming(false)
    }
  }

  return (
    <div className="analyze-page">
      <nav className="analyze-nav">
        <Link to="/" className="analyze-logo"><img src={illusionLogo} alt="Illusion" /></Link>
        <div className="analyze-nav-links">
          <a href="/blog">Blog</a>
          <Link to="/login">Log in</Link>
          <Link to="/register" className="btn-primary-sm analyze-register-link">Start free</Link>
        </div>
      </nav>

      <main className="analyze-main">
        <section className="analyze-hero">
          <div className="analyze-badge"><SearchCheck size={14} /> Free AI website analyzer</div>
          <h1>Audit your website for AI search.</h1>
          <p>
            Get a plain-English audit for customers, Google, and AI answer engines.
            Built for startups and small businesses that need clarity, not enterprise theater.
          </p>
          <form className="analyze-form" onSubmit={submit}>
            <input
              type="text"
              value={url}
              onChange={e => setUrl(e.target.value)}
              placeholder="ecserviceprovider.com"
              required
            />
            <button className="btn-primary" type="submit" disabled={loading}>
              {loading ? <><Loader size={15} className="spin-icon" /> Auditing...</> : <>Audit my site <ArrowRight size={15} /></>}
            </button>
          </form>
          {TURNSTILE_SITE_KEY && (
            <div className="analyze-turnstile">
              <div
                className="cf-turnstile"
                data-sitekey={TURNSTILE_SITE_KEY}
                data-callback="onAuditTurnstileSuccess"
                data-theme="dark"
              />
            </div>
          )}
          {error && <div className="error-msg analyze-error">{error}</div>}
        </section>

        {audit && (
          <section className="analyze-report-shell">
            <WebsiteAuditReport
              audit={audit}
              publicToken={publicToken}
              publicMode
              onClaim={claimAudit}
              claiming={claiming}
            />
          </section>
        )}
      </main>
    </div>
  )
}
