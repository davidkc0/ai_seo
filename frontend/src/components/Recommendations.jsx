import React, { useState, useEffect } from 'react'
import { api } from '../api'
import { Sparkles, TrendingUp, AlertCircle, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react'
import './Recommendations.css'

const PRIORITY_META = {
  high:   { label: 'High', rank: 0 },
  medium: { label: 'Medium', rank: 1 },
  low:    { label: 'Low', rank: 2 },
}

export default function Recommendations({ productId, refreshKey = 0, scanning = false, plan = 'free' }) {
  const [rec, setRec] = useState(null)
  const [overview, setOverview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [expandedAction, setExpandedAction] = useState(null)
  const [showOverview, setShowOverview] = useState(false)

  const isFree = plan === 'free'

  useEffect(() => {
    if (productId && !isFree) load(false)
  }, [productId])

  useEffect(() => {
    if (productId && refreshKey > 0 && !isFree) load(true)
  }, [refreshKey])

  const load = async (silent) => {
    if (!silent) setLoading(true)
    try {
      const [r, ov] = await Promise.all([
        api.getRecommendations(productId).catch(() => null),
        api.getAIOverview(productId).catch(() => null),
      ])
      setRec(r)
      setOverview(ov)
    } finally {
      if (!silent) setLoading(false)
    }
  }

  // Free plan — show upgrade card
  if (isFree) {
    return (
      <div className="card recommendations-card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <h3><Sparkles size={14} className="rec-icon" /> SEO Recommendations</h3>
          <span className="card-hint">Starter plan</span>
        </div>
        <div className="rec-upgrade">
          <div className="rec-upgrade-icon"><Sparkles size={24} /></div>
          <div className="rec-upgrade-text">
            <strong>Unlock AI-powered recommendations</strong>
            <p>Upgrade to Starter to get personalized, AI-powered action items after every scan — plus Google AI Overview tracking and bot traffic analysis.</p>
          </div>
          <a href="/pricing" className="btn-primary" style={{ whiteSpace: 'nowrap' }}>Upgrade →</a>
        </div>
      </div>
    )
  }

  if (loading) return <div className="spinner" />

  // Still-generating state during in-flight scan
  if (scanning && !rec) {
    return (
      <div className="card recommendations-card">
        <div className="card-header">
          <h3><Sparkles size={14} className="rec-icon" /> SEO Recommendations</h3>
          <span className="card-hint">Generating...</span>
        </div>
        <div className="rec-empty">
          <div className="rec-empty-text">
            We're analyzing your scan results + Google AI Overview citations. This usually
            takes 10–15 seconds after the scan finishes.
          </div>
        </div>
      </div>
    )
  }

  if (!rec) return null

  const sortedActions = [...(rec.actions || [])].sort(
    (a, b) => (PRIORITY_META[a.priority]?.rank ?? 3) - (PRIORITY_META[b.priority]?.rank ?? 3)
  )

  return (
    <div className="card recommendations-card" style={{ marginBottom: 24 }}>
      <div className="card-header">
        <h3><Sparkles size={14} className="rec-icon" /> SEO Recommendations</h3>
        <span className="card-hint">
          Based on {rec.based_on_scan_count} LLM response{rec.based_on_scan_count === 1 ? '' : 's'}
          {overview?.was_returned ? ' + Google AI Overview' : ''}
        </span>
      </div>

      {/* Executive summary */}
      <div className="rec-summary">{rec.executive_summary}</div>

      {/* Strengths / Weaknesses */}
      {(rec.strengths?.length > 0 || rec.weaknesses?.length > 0) && (
        <div className="rec-sw-grid">
          {rec.strengths?.length > 0 && (
            <div className="rec-sw-col">
              <div className="rec-sw-label"><TrendingUp size={12} /> Strengths</div>
              <ul className="rec-sw-list">
                {rec.strengths.map((s, i) => <li key={i}>{s}</li>)}
              </ul>
            </div>
          )}
          {rec.weaknesses?.length > 0 && (
            <div className="rec-sw-col">
              <div className="rec-sw-label"><AlertCircle size={12} /> Weaknesses</div>
              <ul className="rec-sw-list">
                {rec.weaknesses.map((s, i) => <li key={i}>{s}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Action list */}
      {sortedActions.length > 0 && (
        <div className="rec-actions">
          <div className="rec-actions-label">Prioritized actions</div>
          {sortedActions.map((a, i) => {
            const open = expandedAction === i
            return (
              <button
                key={i}
                className={`rec-action ${open ? 'open' : ''}`}
                onClick={() => setExpandedAction(open ? null : i)}
              >
                <div className="rec-action-row">
                  <span className={`rec-priority rec-priority-${a.priority}`}>
                    {PRIORITY_META[a.priority]?.label || a.priority}
                  </span>
                  <span className="rec-action-title">{a.title}</span>
                  <span className="rec-action-chevron">
                    {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </span>
                </div>
                {open && a.rationale && (
                  <div className="rec-action-rationale">{a.rationale}</div>
                )}
              </button>
            )
          })}
        </div>
      )}

      {/* Google AI Overview source peek */}
      {overview && (
        <div className="rec-ao-section">
          <button
            className="rec-ao-toggle"
            onClick={() => setShowOverview(s => !s)}
          >
            <span>Google AI Overview source data</span>
            {showOverview ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
          {showOverview && (
            overview.was_returned ? (
              <div className="rec-ao-body">
                <div className="rec-ao-query">Query: "{overview.query}"</div>
                <pre className="rec-ao-text">{overview.overview_text}</pre>
                {overview.references?.length > 0 && (
                  <div className="rec-ao-refs">
                    <div className="rec-ao-refs-label">Cited sources</div>
                    <ol className="rec-ao-refs-list">
                      {overview.references.map((r, i) => (
                        <li key={i}>
                          <a href={r.url} target="_blank" rel="noreferrer">
                            {r.title || r.url} <ExternalLink size={10} />
                          </a>
                          {r.source && <span className="rec-ao-ref-source"> · {r.source}</span>}
                        </li>
                      ))}
                    </ol>
                  </div>
                )}
              </div>
            ) : (
              <div className="rec-ao-body">
                <div className="rec-ao-empty">
                  Google didn't return an AI Overview for this query on the last scan.
                  Only ~36% of queries trigger AI Overview, so this isn't unusual —
                  but it is a signal worth tracking.
                </div>
              </div>
            )
          )}
        </div>
      )}
    </div>
  )
}
