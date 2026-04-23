import React, { useState, useEffect } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../AuthContext'
import { CheckCircle } from 'lucide-react'
import illusionLogo from '../assets/illusion_logo.svg'
import './Auth.css'
import { track } from '../analytics'

export default function Register() {
  const [searchParams] = useSearchParams()
  const [email, setEmail] = useState(searchParams.get('email') || '')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { register } = useAuth()
  const navigate = useNavigate()

  useEffect(() => { track.registerStarted() }, [])

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    if (password.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }
    setLoading(true)
    try {
      await register(email, password)
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
