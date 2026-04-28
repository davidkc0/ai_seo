import React, { useState, useEffect } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../AuthContext'
import { CheckCircle } from 'lucide-react'
import illusionLogo from '../assets/illusion_logo.svg'
import './Auth.css'
import { track } from '../analytics'

// If unset, the Turnstile widget doesn't render and the backend skips
// captcha checks (dev-mode escape hatch). Set in Vercel envs for prod.
const TURNSTILE_SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY || ''

export default function Register() {
  const [searchParams] = useSearchParams()
  const [email, setEmail] = useState(searchParams.get('email') || '')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [turnstileToken, setTurnstileToken] = useState('')
  const { register } = useAuth()
  const navigate = useNavigate()

  useEffect(() => { track.registerStarted() }, [])

  // Inject the Turnstile script + window callback once on mount. We use a
  // global callback (rather than @marsidev/react-turnstile or similar) so
  // we don't pull a new dependency for ~30 lines of glue.
  useEffect(() => {
    if (!TURNSTILE_SITE_KEY) return
    window.onTurnstileSuccess = (token) => setTurnstileToken(token)
    const existing = document.querySelector('script[data-turnstile]')
    if (existing) return
    const s = document.createElement('script')
    s.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js'
    s.async = true
    s.defer = true
    s.dataset.turnstile = '1'
    document.body.appendChild(s)
    return () => {
      delete window.onTurnstileSuccess
    }
  }, [])

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    if (password.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }
    if (TURNSTILE_SITE_KEY && !turnstileToken) {
      setError('Please complete the captcha to continue.')
      return
    }
    setLoading(true)
    try {
      await register(email, password, turnstileToken)
      track.registerCompleted('organic')
      navigate('/dashboard')
    } catch (err) {
      setError(err.message)
      track.registerFailed(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo"><img src={illusionLogo} alt="Illusion" /></div>
        <h1>Start your free trial</h1>
        <p className="auth-sub">7 days free · No credit card required</p>

        {error && <div className="auth-error"><span className="auth-error-icon">!</span> {error}</div>}

        <form onSubmit={submit}>
          <div className="form-group">
            <label>Work email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@company.com"
              required
              autoFocus
            />
          </div>
          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="Min. 8 characters"
              required
            />
          </div>
          {TURNSTILE_SITE_KEY && (
            <div className="form-group" style={{ display: 'flex', justifyContent: 'center' }}>
              <div
                className="cf-turnstile"
                data-sitekey={TURNSTILE_SITE_KEY}
                data-callback="onTurnstileSuccess"
                data-theme="dark"
              />
            </div>
          )}
          <button type="submit" className="btn-primary auth-submit" disabled={loading}>
            {loading ? 'Creating account...' : 'Create account →'}
          </button>
        </form>

        <div className="trial-info">
          <div><CheckCircle size={12} /> 7-day free trial</div>
          <div><CheckCircle size={12} /> 1 product, 3 keywords</div>
          <div><CheckCircle size={12} /> Weekly AI scans</div>
        </div>

        <div className="auth-footer">
          Already have an account? <Link to="/login">Log in</Link>
        </div>
      </div>
    </div>
  )
}
