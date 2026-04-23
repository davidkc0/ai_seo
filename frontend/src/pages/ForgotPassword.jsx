import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import illusionLogo from '../assets/illusion_logo.svg'
import './Auth.css'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await api.forgotPassword(email)
      setSent(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo"><img src={illusionLogo} alt="Illusion" /></div>
        <h1>Reset your password</h1>
        <p className="auth-sub">We'll email you a reset link</p>

        {error && <div className="auth-error"><span className="auth-error-icon">!</span> {error}</div>}

        {sent ? (
          <div className="auth-success">
            Check your inbox — if an account exists for {email}, we sent a reset link. It expires in 30 minutes.
          </div>
        ) : (
          <form onSubmit={submit}>
            <div className="form-group">
              <label>Email</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@company.com"
                required
                autoFocus
              />
            </div>
            <button type="submit" className="btn-primary auth-submit" disabled={loading}>
              {loading ? 'Sending...' : 'Send reset link →'}
            </button>
          </form>
        )}

        <div className="auth-footer">
          Remember your password? <Link to="/login">Log in</Link>
        </div>
      </div>
    </div>
  )
}
