import React, { useEffect, useState, useRef } from 'react'
import { Link, useSearchParams, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../AuthContext'
import illusionLogo from '../assets/illusion_logo.svg'
import './Auth.css'

export default function VerifyEmail() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''
  const [status, setStatus] = useState('loading') // 'loading' | 'success' | 'error'
  const [error, setError] = useState('')
  const [resending, setResending] = useState(false)
  const [resendNote, setResendNote] = useState('')
  const navigate = useNavigate()
  const { user } = useAuth()
  // Strict mode mounts effects twice in dev — guard against double-firing the
  // verify call (it's idempotent backend-side but the second call still runs).
  const ranRef = useRef(false)

  useEffect(() => {
    if (ranRef.current) return
    ranRef.current = true

    if (!token) {
      setStatus('error')
      setError('Missing verification token. Please use the link from your email.')
      return
    }

    api.verifyEmail(token)
      .then(() => setStatus('success'))
      .catch((e) => {
        setStatus('error')
        setError(e.message || 'Verification failed.')
      })
  }, [token])

  const handleResend = async () => {
    setResending(true)
    setResendNote('')
    try {
      await api.resendVerification()
      setResendNote('A new verification link is on its way.')
    } catch (e) {
      setResendNote(e.message || 'Could not resend. Try again in a minute.')
    } finally {
      setResending(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo"><img src={illusionLogo} alt="Illusion" /></div>
        <h1>Verify your email</h1>

        {status === 'loading' && (
          <p className="auth-sub">Confirming your email...</p>
        )}

        {status === 'success' && (
          <>
            <div className="auth-success">
              Email verified. You're all set — AI scans are now unlocked.
            </div>
            <button
              type="button"
              className="btn-primary auth-submit"
              onClick={() => navigate('/dashboard')}
            >
              Go to dashboard →
            </button>
          </>
        )}

        {status === 'error' && (
          <>
            <div className="auth-error"><span className="auth-error-icon">!</span> {error}</div>
            {user ? (
              <button
                type="button"
                className="btn-primary auth-submit"
                onClick={handleResend}
                disabled={resending}
              >
                {resending ? 'Sending...' : 'Send a new link →'}
              </button>
            ) : (
              <Link to="/login" className="btn-primary auth-submit" style={{ textAlign: 'center', textDecoration: 'none', display: 'block' }}>
                Log in to request a new link →
              </Link>
            )}
            {resendNote && (
              <p className="auth-sub" style={{ marginTop: 14 }}>{resendNote}</p>
            )}
          </>
        )}

        <div className="auth-footer">
          <Link to="/login">Back to login</Link>
        </div>
      </div>
    </div>
  )
}
