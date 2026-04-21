import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../AuthContext'
import { api } from '../api'
import './Settings.css'

export default function Settings() {
  const { user, logout } = useAuth()
  const [notif, setNotif] = useState(null)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    api.getNotifications().then(setNotif).catch(console.error)
  }, [])

  const save = async () => {
    setSaving(true)
    setMsg('')
    try {
      await api.updateNotifications(notif)
      setMsg('success:Settings saved!')
    } catch (e) {
      setMsg(`error:${e.message}`)
    } finally {
      setSaving(false)
    }
  }

  const openPortal = async () => {
    try {
      const { portal_url } = await api.createPortal()
      window.open(portal_url, '_blank')
    } catch (e) {
      setMsg(`error:${e.message}`)
    }
  }

  return (
    <div className="settings-page">
      <div className="settings-header">
        <Link to="/dashboard" className="back-link">← Dashboard</Link>
        <h1>Settings</h1>
      </div>

      <div className="settings-grid">
        {/* Account */}
        <div className="card">
          <h2>Account</h2>
          <div className="setting-row">
            <div>
              <div className="setting-label">Email</div>
              <div className="setting-value">{user?.email}</div>
            </div>
          </div>
          <div className="setting-row">
            <div>
              <div className="setting-label">Plan</div>
              <div className="setting-value plan-display">
                <strong>{user?.plan || 'free'}</strong>
                <Link to="/pricing" className="upgrade-link">Upgrade →</Link>
              </div>
            </div>
          </div>
          {user?.plan !== 'free' && (
            <button className="btn-ghost" onClick={openPortal} style={{ marginTop: 12 }}>
              Manage billing →
            </button>
          )}
        </div>

        {/* Notifications */}
        {notif && (
          <div className="card">
            <h2>Notifications</h2>

            <div className="toggle-row">
              <div>
                <div className="setting-label">Weekly digest</div>
                <div className="toggle-hint">Email every Monday with your AI mention summary</div>
              </div>
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={notif.weekly_digest}
                  onChange={e => setNotif(n => ({ ...n, weekly_digest: e.target.checked }))}
                />
                <span className="toggle-slider" />
              </label>
            </div>

            <div className="toggle-row">
              <div>
                <div className="setting-label">Mention alerts</div>
                <div className="toggle-hint">
                  Get notified instantly when you're mentioned
                  {user?.plan !== 'growth' && <span className="plan-lock"> (Growth plan)</span>}
                </div>
              </div>
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={notif.mention_alerts}
                  disabled={user?.plan !== 'growth'}
                  onChange={e => setNotif(n => ({ ...n, mention_alerts: e.target.checked }))}
                />
                <span className="toggle-slider" />
              </label>
            </div>

            <div className="form-group" style={{ marginTop: 16 }}>
              <label>Alert email</label>
              <input
                value={notif.alert_email || ''}
                onChange={e => setNotif(n => ({ ...n, alert_email: e.target.value }))}
                placeholder={user?.email}
                type="email"
              />
            </div>

            {msg && (
              <div className={msg.startsWith('error:') ? 'error-msg' : 'success-msg'}>
                {msg.replace(/^(error|success):/, '')}
              </div>
            )}

            <button className="btn-primary" onClick={save} disabled={saving}>
              {saving ? 'Saving...' : 'Save settings'}
            </button>
          </div>
        )}

        {/* Danger zone */}
        <div className="card danger-card">
          <h2>Account</h2>
          <button className="btn-ghost danger-btn" onClick={logout}>
            Log out →
          </button>
        </div>
      </div>
    </div>
  )
}
