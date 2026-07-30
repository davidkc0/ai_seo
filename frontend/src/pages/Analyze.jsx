import React, { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { ArrowRight, Check, Copy, Loader, Mail, SearchCheck, X } from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../AuthContext'
import WebsiteAuditReport from '../components/WebsiteAuditReport'
import Seo from '../components/Seo'
import SiteFooter from '../components/SiteFooter'
import { ChatGptLogo, ClaudeLogo, GoogleAIOverviewsLogo } from '../components/AnswerEngineLogos'
import illusionLogo from '../assets/illusion_logo.svg'
import { track } from '../analytics'
import { buildAuditBuyerQuestions } from '../auditPrompts'
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

function leadSourceFromUrl() {
  const params = new URLSearchParams(window.location.search)
  return params.get('utm_content') || params.get('utm_source') || 'public'
}

function normalizeWebsiteInput(value) {
  const trimmed = value.trim()
  if (!trimmed) throw new Error('Enter a website URL.')
  const withProtocol = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`
  let parsed
  try {
    parsed = new URL(withProtocol)
  } catch {
    throw new Error('Enter a valid website URL.')
  }
  if (!['http:', 'https:'].includes(parsed.protocol) || !parsed.hostname.includes('.')) {
    throw new Error('Enter a valid public website URL.')
  }
  parsed.hash = ''
  return parsed.toString()
}

function isValidEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim())
}

export default function Analyze() {
  const { publicToken: routePublicToken } = useParams()
  const isSharedReport = Boolean(routePublicToken)
  const [url, setUrl] = useState('')
  const [email, setEmail] = useState('')
  const [modalUrl, setModalUrl] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [modalStep, setModalStep] = useState('details')
  const [modalError, setModalError] = useState('')
  const [audit, setAudit] = useState(null)
  const [publicToken, setPublicToken] = useState(routePublicToken || '')
  const [shareUrl, setShareUrl] = useState(routePublicToken ? `${window.location.origin}/analyze/${routePublicToken}` : '')
  const [turnstileToken, setTurnstileToken] = useState('')
  const [loading, setLoading] = useState(false)
  const [modalSubmitting, setModalSubmitting] = useState(false)
  const [claiming, setClaiming] = useState(false)
  const [startingScan, setStartingScan] = useState(false)
  const [bookingReview, setBookingReview] = useState(false)
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState('')
  const completedRef = useRef(false)
  const pollRef = useRef(null)
  const { user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const reviewBooked = new URLSearchParams(location.search).get('review') === 'booked'

  useEffect(() => {
    if (reviewBooked) track.founderReviewCheckoutCompleted()
  }, [reviewBooked])

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

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  const handleAuditData = (data) => {
    setAudit(data)
    if (data.public_token) setPublicToken(data.public_token)
    if (data.share_url) setShareUrl(data.share_url)
    if (data.normalized_url) setUrl(data.normalized_url)
    if (data.status === 'completed' || data.status === 'failed') {
      stopPolling()
      setLoading(false)
      if (data.status === 'completed' && !completedRef.current) {
        completedRef.current = true
        track.auditCompleted(data.scores?.overall)
      }
    }
  }

  const pollAudit = (id, token) => {
    stopPolling()
    pollRef.current = setInterval(async () => {
      try {
        const data = await api.getPublicWebsiteAudit(id, token)
        handleAuditData(data)
      } catch (e) {
        setError(e.message)
        setLoading(false)
        stopPolling()
      }
    }, 3500)
  }

  const pollSharedAudit = (token) => {
    stopPolling()
    pollRef.current = setInterval(async () => {
      try {
        const data = await api.getSharedWebsiteAudit(token)
        handleAuditData(data)
      } catch (e) {
        setError(e.message)
        setLoading(false)
        stopPolling()
      }
    }, 3500)
  }

  useEffect(() => {
    if (!routePublicToken) return
    completedRef.current = false
    setError('')
    setAudit(null)
    setLoading(true)
    setPublicToken(routePublicToken)
    setShareUrl(`${window.location.origin}/analyze/${routePublicToken}`)

    let cancelled = false
    api.getSharedWebsiteAudit(routePublicToken)
      .then((data) => {
        if (cancelled) return
        handleAuditData(data)
        if (data.status !== 'completed' && data.status !== 'failed') {
          pollSharedAudit(routePublicToken)
        }
      })
      .catch((e) => {
        if (cancelled) return
        setError(e.message)
        setLoading(false)
      })

    return () => {
      cancelled = true
      stopPolling()
    }
  }, [routePublicToken])

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setModalError('')
    completedRef.current = false
    if (TURNSTILE_SITE_KEY && !turnstileToken) {
      setError('Please complete the captcha to continue.')
      return
    }
    try {
      const normalized = normalizeWebsiteInput(url)
      setUrl(normalized)
      setModalUrl(normalized)
      setModalStep('details')
      setModalOpen(true)
      track.auditEmailModalOpened(leadSourceFromUrl())
    } catch (e) {
      setError(e.message)
    }
  }

  const startAuditFromModal = async (e) => {
    e.preventDefault()
    setModalError('')
    completedRef.current = false

    let normalized
    try {
      normalized = normalizeWebsiteInput(modalUrl)
    } catch (err) {
      setModalError(err.message)
      return
    }

    if (!isValidEmail(email)) {
      setModalError('Enter a valid email address.')
      return
    }

    const source = leadSourceFromUrl()
    setModalSubmitting(true)
    setLoading(true)
    try {
      const start = await api.startPublicWebsiteAudit({
        url: normalized,
        email: email.trim(),
        turnstile_token: turnstileToken || null,
        lead_source: source,
      })
      track.auditEmailSubmitted(source)
      track.auditStarted(source)
      setPublicToken(start.public_token)
      setShareUrl(start.share_url || `${window.location.origin}/analyze/${start.public_token}`)
      setModalUrl(normalized)
      setUrl(normalized)
      setModalStep('generating')
      try {
        const initial = await api.getPublicWebsiteAudit(start.audit_id, start.public_token)
        handleAuditData(initial)
        if (initial.status !== 'completed' && initial.status !== 'failed') {
          pollAudit(start.audit_id, start.public_token)
        }
      } catch {
        pollAudit(start.audit_id, start.public_token)
      }
    } catch (e) {
      setModalStep('details')
      setModalError(e.message)
      setLoading(false)
    } finally {
      setModalSubmitting(false)
    }
  }

  const closeModal = () => {
    setModalOpen(false)
  }

  const goToSharedReport = () => {
    closeModal()
    const token = publicToken || audit?.public_token
    if (token) navigate(`/analyze/${token}`)
  }

  const copyShareLink = async () => {
    const link = shareUrl || `${window.location.origin}/analyze/${publicToken || routePublicToken}`
    try {
      await navigator.clipboard.writeText(link)
    } catch {
      const input = document.createElement('input')
      input.value = link
      document.body.appendChild(input)
      input.select()
      document.execCommand('copy')
      document.body.removeChild(input)
    }
    setCopied(true)
    track.auditReportLinkCopied()
    window.setTimeout(() => setCopied(false), 1800)
  }

  const continueFromAudit = (intent = 'save') => {
    const token = publicToken || audit?.public_token || routePublicToken
    if (!audit || !token) return
    const questions = buildAuditBuyerQuestions(audit)
    const pending = {
      audit_id: audit.id,
      public_token: token,
      url: audit.normalized_url || url,
      intent,
      keywords: intent === 'first_scan' ? questions : [],
    }
    localStorage.setItem('pendingWebsiteAudit', JSON.stringify(pending))

    if (!user) {
      track.signupFromAudit()
      navigate(`/register?source=${intent === 'first_scan' ? 'audit-scan' : 'audit'}`)
      return
    }

    if (user.email_verified !== true) {
      navigate(`/verify-email?source=${intent === 'first_scan' ? 'audit-scan' : 'audit'}`)
      return
    }

    navigate(intent === 'first_scan' ? '/dashboard?from=audit-scan' : '/dashboard?tab=audit')
  }

  const claimAudit = () => {
    setClaiming(true)
    try {
      continueFromAudit('save')
    } finally {
      setClaiming(false)
    }
  }

  const startVisibilityScan = () => {
    const questions = buildAuditBuyerQuestions(audit)
    setStartingScan(true)
    track.auditVisibilityScanClicked(questions.length)
    try {
      continueFromAudit('first_scan')
    } finally {
      setStartingScan(false)
    }
  }

  const bookFounderReview = async () => {
    const token = publicToken || audit?.public_token || routePublicToken
    if (!token) return
    setBookingReview(true)
    setError('')
    try {
      track.founderReviewCheckoutStarted()
      const { checkout_url } = await api.createAuditReviewCheckout(token)
      window.location.href = checkout_url
    } catch (e) {
      setError(e.message)
      setBookingReview(false)
    }
  }

  const requestWebsiteCleanup = () => {
    track.websiteCleanupRequested()
    const domain = audit?.domain || audit?.normalized_url || 'my website'
    const subject = encodeURIComponent(`Website cleanup request for ${domain}`)
    const body = encodeURIComponent(
      `Hi David,\n\nI ran an Illusion website audit for ${domain} and would like a flat-fee quote to handle the recommended fixes.\n\nReport: ${shareUrl || window.location.href}\n\nThanks,`
    )
    window.location.href = `mailto:david@illusion.ai?subject=${subject}&body=${body}`
  }

  const renderShareTools = () => {
    const token = publicToken || routePublicToken || audit?.public_token
    if (!token) return null
    const link = shareUrl || `${window.location.origin}/analyze/${token}`
    return (
      <div className="analyze-share-tools">
        <div>
          <span>Shareable report</span>
          <strong>{link}</strong>
        </div>
        <button type="button" className="btn-ghost" onClick={copyShareLink}>
          {copied ? <Check size={14} /> : <Copy size={14} />}
          {copied ? 'Copied' : 'Copy link'}
        </button>
      </div>
    )
  }

  const renderEmailModal = () => {
    if (!modalOpen) return null
    return (
      <div className="analyze-modal-backdrop" role="presentation">
        <div className={`analyze-modal ${modalStep === 'generating' ? 'analyze-modal-generating' : ''}`} role="dialog" aria-modal="true" aria-labelledby="analyze-modal-title">
          <button type="button" className="analyze-modal-close" onClick={closeModal} aria-label="Close">
            <X size={18} />
          </button>

          {modalStep === 'details' ? (
            <form onSubmit={startAuditFromModal}>
              <h2 id="analyze-modal-title">Get your free AI website audit</h2>
              <p className="analyze-modal-sub">We'll email it to you in minutes.</p>

              <label className="analyze-modal-field">
                <span>Your site URL <b>*</b></span>
                <input
                  type="text"
                  value={modalUrl}
                  onChange={e => setModalUrl(e.target.value)}
                  required
                />
              </label>

              <label className="analyze-modal-field">
                <span>Work email <b>*</b></span>
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  required
                />
              </label>

              <p className="analyze-modal-note">We'll email your report and may follow up with practical fixes.</p>
              {modalError && <div className="error-msg analyze-modal-error">{modalError}</div>}

              <div className="analyze-modal-actions">
                <button className="btn-primary" type="submit" disabled={modalSubmitting}>
                  {modalSubmitting ? <><Loader size={15} className="spin-icon" /> Starting...</> : <>Get AI Website Audit <ArrowRight size={15} /></>}
                </button>
              </div>
            </form>
          ) : (
            <div className="analyze-generating-panel">
              <div className="analyze-generating-icon">
                <Mail size={34} />
              </div>
              <h2 id="analyze-modal-title">Your AI Website Audit will be ready soon</h2>
              <p>
                We'll email the report to {email.trim() || 'your inbox'} when it is generated.
                You can keep this page open or come back from the report link.
              </p>
              <button className="btn-primary" type="button" onClick={goToSharedReport} disabled={!publicToken}>
                Got it
              </button>
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="analyze-page">
      <Seo
        title="Free AI Website Analyzer for AI Search, SEO, and Local Business Visibility"
        description="Run a free AI website audit for customer clarity, SEO, local SEO, and AI search readiness. Built for startups and small businesses."
        path={isSharedReport ? `/analyze/${routePublicToken}` : '/analyze'}
      />
      <nav className="analyze-nav">
        <Link to="/" className="analyze-logo"><img src={illusionLogo} alt="Illusion" /></Link>
        <div className="analyze-nav-links">
          <a href="/blog">Blog</a>
          <Link to="/login">Log in</Link>
          <Link to="/register" className="btn-primary-sm analyze-register-link">Start free</Link>
        </div>
      </nav>

      <main className={`analyze-main ${isSharedReport ? 'analyze-main-report' : ''}`}>
        {isSharedReport ? (
          <>
            <section className="analyze-share-hero">
              <div className="analyze-badge"><SearchCheck size={14} /> AI website audit</div>
              <h1>{audit?.domain || 'Your website audit'}</h1>
              <p>
                This shareable report checks customer clarity, SEO/local SEO, trust signals,
                crawlability, and AI-search readiness.
              </p>
            </section>
            {renderShareTools()}
            {reviewBooked && (
              <div className="success-msg analyze-review-success">
                Founder review purchased. David will follow up at the audit email within one business day.
              </div>
            )}
            {error && <div className="error-msg analyze-error">{error}</div>}
            <section className="analyze-report-shell">
              {audit ? (
                <WebsiteAuditReport
                  audit={audit}
                  publicToken={publicToken || routePublicToken}
                  publicMode
                  onClaim={claimAudit}
                  claiming={claiming}
                  onStartScan={startVisibilityScan}
                  startingScan={startingScan}
                  onBookReview={bookFounderReview}
                  bookingReview={bookingReview}
                  onRequestCleanup={requestWebsiteCleanup}
                />
              ) : (
                <div className="audit-progress">
                  <SparklesFallback />
                  <div>
                    <strong>{loading ? 'Loading report...' : 'Report not found'}</strong>
                    <span>{loading ? 'Checking whether the audit is ready.' : 'Try running a new website audit.'}</span>
                  </div>
                </div>
              )}
            </section>
          </>
        ) : (
          <>
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
                <button className="btn-primary" type="submit" disabled={loading || modalSubmitting}>
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
              <>
                {renderShareTools()}
                <section className="analyze-report-shell">
                  <WebsiteAuditReport
                    audit={audit}
                    publicToken={publicToken}
                    publicMode
                    onClaim={claimAudit}
                    claiming={claiming}
                    onStartScan={startVisibilityScan}
                    startingScan={startingScan}
                    onBookReview={bookFounderReview}
                    bookingReview={bookingReview}
                    onRequestCleanup={requestWebsiteCleanup}
                  />
                </section>
              </>
            )}
          </>
        )}
      </main>
      {renderEmailModal()}
      <SiteFooter />
    </div>
  )
}

function SparklesFallback() {
  return <Loader size={16} className="spin-icon" />
}
