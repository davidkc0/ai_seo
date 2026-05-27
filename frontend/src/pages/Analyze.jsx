import React, { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, Loader, SearchCheck } from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../AuthContext'
import WebsiteAuditReport from '../components/WebsiteAuditReport'
import Seo from '../components/Seo'
import SiteFooter from '../components/SiteFooter'
import { ChatGptLogo, ClaudeLogo, GoogleAIOverviewsLogo } from '../components/AnswerEngineLogos'
import illusionLogo from '../assets/illusion_logo.svg'
import { track } from '../analytics'
import './Analyze.css'

const TURNSTILE_SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY || ''

const answerPlatforms = [
  {
    name: 'ChatGPT',
    Logo: ChatGptLogo,
    tone: 'chatgpt',
    description: 'Check whether your site makes your services, audience, and proof easy for ChatGPT to understand.',
  },
  {
    name: 'Claude',
    Logo: ClaudeLogo,
    tone: 'claude',
    description: 'See whether Claude has enough clean context to describe what you do without guessing.',
  },
  {
    name: 'Google AI Overviews',
    Logo: GoogleAIOverviewsLogo,
    tone: 'google',
    description: 'Spot crawlability, local SEO, and content gaps that can keep Google from citing your pages.',
  },
]

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
      const params = new URLSearchParams(window.location.search)
      track.auditStarted(params.get('utm_content') || params.get('utm_source') || 'public')
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

    if (user.email_verified !== true) {
      navigate('/verify-email?source=audit')
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
      <Seo
        title="Free AI Website Analyzer for AI Search, SEO, and Local Business Visibility"
        description="Run a free AI website audit for customer clarity, SEO, local SEO, and AI search readiness. Built for startups and small businesses."
        path="/analyze"
      />
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
          <h1>Know where your website stands <span className="analyze-serif">in</span> AI search.</h1>
          <p>
            Run a plain-English audit for customers, Google, and AI answer engines.
            See what to fix first — without the enterprise SEO theater.
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

        <section className="answer-platforms" aria-labelledby="answer-platforms-title">
          <div className="answer-platforms-header">
            <div>
              <span className="answer-platforms-kicker">Answer engine coverage</span>
              <h2 id="answer-platforms-title">Optimize your website for the AI answer engines your customers use</h2>
            </div>
            <p>
              Illusion checks whether your site gives ChatGPT, Claude, and Google AI Overviews
              the clear services, trust signals, local context, and crawlable content they need
              to understand your business.
            </p>
          </div>
          <div className="answer-platforms-grid">
            {answerPlatforms.map(({ name, Logo, tone, description }) => (
              <article className="answer-platform-card" key={name}>
                <div className={`answer-platform-logo answer-platform-logo-${tone}`}>
                  <Logo className="answer-platform-logo-mark" />
                </div>
                <div>
                  <h3>{name}</h3>
                  <p>{description}</p>
                </div>
              </article>
            ))}
          </div>
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
      <SiteFooter />
    </div>
  )
}
