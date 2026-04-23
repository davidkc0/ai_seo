import React, { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import illusionLogo from '../assets/illusion_logo.svg'
import './Auth.css'

export default function ResetPassword() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError('')

    if (password.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }
    if (password !== confirm) {
      setError('Passwords do not match')
      return
    }
    if (!token) {
      setError('Missing reset token. Please use the link from your email.')
      return
    }

    setLoading(true)
    try {
      await api.resetPassword(token, password)
      setSuccess(true)
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
        <h1>Choose a new password</h1>
        <p className="auth-sub">Must be at least 8 characters</p>

        {error && <div className="auth-error"><span className="auth-error-icon">!</span> {error}</div>}

        {success ? (
          <>
            <div className="auth-success">
              Password updated successfully.
            </div>
            <Link to="/login" className="btn-primary auth-submit" style={{ textAlign: 'center', textDecoration: 'none', display: 'block' }}>
              Log in →
            </Link>
          </>
        ) : (
          <form onSubmit={submit}>
            <div className="form-group">
              <label>New password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="Min. 8 characters"
                required
                autoFocus
              />
            </div>
            <div className="form-group">
              <label>Confirm password</label>
              <input
                type="password"
                value={confirm}
                onChange={e => setConfirm(e.target.value)}
                placeholder="Re-enter password"
                required
              />
            </div>
            <button type="submit" className="btn-primary auth-submit" disabled={loading}>
              {loading ? 'Updating...' : 'Update password →'}
            </button>
          </form>
        )}

        <div className="auth-footer">
          <Link to="/login">Back to login</Link>
        </div>
      </div>
    </div>
  )
}
