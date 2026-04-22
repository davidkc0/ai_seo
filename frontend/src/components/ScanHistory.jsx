import React, { useState, useEffect } from 'react'
import { api } from '../api'
import { Clock, TrendingUp, TrendingDown, Minus, ChevronDown, ChevronUp } from 'lucide-react'
import './ScanHistory.css'

export default function ScanHistory({ productId, refreshKey = 0 }) {
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    if (productId) load()
  }, [productId])

  useEffect(() => {
    if (productId && refreshKey > 0) load()
  }, [refreshKey])

  const load = async () => {
    try {
      const data = await api.getScanHistory(productId)
      setHistory(data)
    } catch (e) {
      console.error(e)
    }
  }

  if (history.length === 0) return null

  const sentimentIcon = (s) => {
    if (s === 'positive') return <TrendingUp size={12} className="sentiment-positive" />
    if (s === 'negative') return <TrendingDown size={12} className="sentiment-negative" />
    return <Minus size={12} className="sentiment-neutral" />
  }

  const formatDate = (iso) => {
    const d = new Date(iso)
    const now = new Date()
    const diffMs = now - d
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

    if (diffHours < 1) return 'Just now'
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays === 1) return 'Yesterday'
    if (diffDays < 7) return `${diffDays}d ago`
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  const displayHistory = expanded ? history : history.slice(0, 5)

  return (
    <div className="card scan-history-card" style={{ marginBottom: 24 }}>
      <div className="card-header">
        <h3><Clock size={14} style={{ marginRight: 6, verticalAlign: -2 }} /> Scan History</h3>
        <span className="card-hint">{history.length} scan{history.length !== 1 ? 's' : ''}</span>
      </div>

      <div className="scan-history-list">
        {displayHistory.map((scan, i) => {
          const rateColor = scan.mention_rate >= 70 ? 'var(--success)' : scan.mention_rate >= 40 ? 'var(--warning)' : 'var(--text-dim)'
          const trend = i < displayHistory.length - 1
            ? scan.mention_rate - displayHistory[i + 1].mention_rate
            : 0

          return (
            <div key={i} className="scan-history-row">
              <div className="scan-history-date">{formatDate(scan.scan_date)}</div>
              <div className="scan-history-stats">
                <span className="scan-history-rate" style={{ color: rateColor }}>
                  {scan.mention_rate}%
                </span>
                {trend !== 0 && (
                  <span className={`scan-history-trend ${trend > 0 ? 'up' : 'down'}`}>
                    {trend > 0 ? '↑' : '↓'}{Math.abs(trend)}%
                  </span>
                )}
                <span className="scan-history-detail">
                  {scan.mentions}/{scan.total_queries} mentions
                </span>
                {scan.best_position && (
                  <span className="scan-history-pos">
                    Best: #{scan.best_position}
                  </span>
                )}
                <span className="scan-history-sentiment">
                  {sentimentIcon(scan.top_sentiment)}
                </span>
              </div>
              <div className="scan-history-providers">
                {scan.providers?.map(p => (
                  <span key={p} className="scan-history-provider">{p}</span>
                ))}
              </div>
            </div>
          )
        })}
      </div>

      {history.length > 5 && (
        <button className="scan-history-toggle" onClick={() => setExpanded(!expanded)}>
          {expanded ? (
            <><ChevronUp size={14} /> Show less</>
          ) : (
            <><ChevronDown size={14} /> Show all {history.length} scans</>
          )}
        </button>
      )}
    </div>
  )
}
