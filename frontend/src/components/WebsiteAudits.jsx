import React, { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Globe, Loader, RefreshCw } from 'lucide-react'
import { api } from '../api'
import WebsiteAuditReport from './WebsiteAuditReport'
import { track } from '../analytics'
import './WebsiteAudits.css'

export default function WebsiteAudits({ product = null, refreshProducts }) {
  const [audits, setAudits] = useState([])
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [url, setUrl] = useState(product?.website_url || '')
  const [message, setMessage] = useState('')
  const pollRef = useRef(null)

  useEffect(() => {
    setUrl(product?.website_url || '')
    loadAudits(false)
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [product?.id, product?.website_url])

  const loadAudits = async (silent = true) => {
    if (!silent) setLoading(true)
    try {
      const data = await api.listWebsiteAudits(product?.id)
      setAudits(data)
      const hasActive = data.some(a => a.status === 'queued' || a.status === 'running')
      setRunning(hasActive)
      if (hasActive && !pollRef.current) {
        startPolling()
      }
      if (!hasActive && pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    } catch (e) {
      setMessage(`error:${e.message}`)
    } finally {
      if (!silent) setLoading(false)
    }
  }

  const startPolling = () => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(() => loadAudits(true), 4000)
  }

  const runAudit = async (e) => {
    e.preventDefault()
    setMessage('')
    setRunning(true)
    try {
      await api.rerunWebsiteAudit({ product_id: product?.id || null, url: url || null })
      track.auditRerun()
      await refreshProducts?.()
      await loadAudits(true)
      startPolling()
    } catch (err) {
      setRunning(false)
      setMessage(`error:${err.message}`)
    }
  }

  const latest = audits[0]
  const msgType = message.startsWith('error:') ? 'error' : 'success'
  const msgText = message.replace(/^(error|success):/, '')

  if (loading) return <div className="spinner" />

  if (!product && audits.length === 0) {
    return (
      <div className="audit-empty-state">
        <Globe size={36} />
        <h3>No saved website audits yet</h3>
        <p>Run the public analyzer, then save the report to keep it in your dashboard.</p>
        <Link to="/analyze" className="btn-primary">Open analyzer</Link>
      </div>
    )
  }

  return (
    <div className="website-audits">
      <div className="audit-dashboard-header">
        <div>
          <h2>Website Audit</h2>
          <p>
            {product
              ? 'Check whether this website is clear for customers, Google, and AI answer engines.'
              : 'Saved public audits from your account.'}
          </p>
        </div>
        <Link to="/analyze" className="btn-ghost">Public analyzer</Link>
      </div>

      {product && (
        <form className="audit-rerun-card" onSubmit={runAudit}>
          <div>
            <label>Website URL</label>
            <input
              value={url}
              onChange={e => setUrl(e.target.value)}
              placeholder="https://example.com"
              required
            />
          </div>
          <button className="btn-primary" type="submit" disabled={running}>
            {running ? <><Loader size={14} className="spin-icon" /> Auditing...</> : <><RefreshCw size={14} /> Run audit</>}
          </button>
        </form>
      )}

      {message && (
        <div className={msgType === 'error' ? 'error-msg' : 'success-msg'}>{msgText}</div>
      )}

      {latest ? (
        <div className="card audit-dashboard-report">
          <WebsiteAuditReport audit={latest} />
        </div>
      ) : product ? (
        <div className="audit-empty-state compact">
          <Globe size={30} />
          <h3>No audit yet</h3>
          <p>Add the website URL and run the first audit.</p>
        </div>
      ) : null}

      {audits.length > 1 && (
        <div className="card audit-history-card">
          <div className="card-header">
            <h3>Audit history</h3>
            <span className="card-hint">{audits.length} reports</span>
          </div>
          <div className="audit-history-list">
            {audits.slice(1).map(a => (
              <div className="audit-history-row" key={a.id}>
                <span>{new Date(a.created_at).toLocaleDateString()}</span>
                <strong>{a.scores?.overall ?? '-'} / 100</strong>
                <small>{a.status}</small>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
