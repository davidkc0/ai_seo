import React, { useState, useEffect } from 'react'
import { api } from '../api'
import './ScanResults.css'

export default function ScanResults({ productId, refreshKey = 0 }) {
  const [results, setResults] = useState([])
  const [expanded, setExpanded] = useState(null)
  const [loading, setLoading] = useState(false)

  // Initial load / product change — show spinner
  useEffect(() => {
    if (productId) loadResults(false)
  }, [productId])

  // Silent refresh triggered by parent (e.g. during an in-flight scan)
  useEffect(() => {
    if (productId && refreshKey > 0) loadResults(true)
  }, [refreshKey])

  const loadResults = async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      const data = await api.getResults(productId, 20)
      setResults(data)
    } catch (e) {
      console.error(e)
    } finally {
      if (!silent) setLoading(false)
    }
  }

  if (loading) return <div className="spinner" />
  if (!results.length) return null

  return (
    <div className="card" style={{ marginTop: 24 }}>
      <div className="card-header">
        <h3>Full AI Responses</h3>
        <span className="card-hint">Click any query to read the full response</span>
      </div>
      <div className="results-list">
        {results.map(r => (
          <div key={r.id} className="result-item">
            <button
              className="result-toggle"
              onClick={() => setExpanded(expanded === r.id ? null : r.id)}
            >
              <div className="result-header">
                <div className={`scan-dot ${r.product_mentioned ? 'green' : 'gray'}`} />
                <span className="result-query">"{r.query}"</span>
              </div>
              <div className="result-meta">
                {r.product_mentioned ? (
                  <span className="badge badge-green">
                    Mentioned {r.mention_position ? `#${r.mention_position}` : ''}
                  </span>
                ) : (
                  <span className="badge badge-gray">Not mentioned</span>
                )}
                {r.mention_sentiment && (
                  <span className={`badge badge-${
                    r.mention_sentiment === 'positive' ? 'green' :
                    r.mention_sentiment === 'negative' ? 'yellow' : 'gray'
                  }`}>
                    {r.mention_sentiment}
                  </span>
                )}
                <span className="result-date">
                  {new Date(r.created_at).toLocaleDateString()}
                </span>
                <span className="expand-icon">{expanded === r.id ? '▲' : '▼'}</span>
              </div>
            </button>
            {expanded === r.id && (
              <div className="result-response">
                <div className="response-label">AI Response ({r.ai_model || 'AI'}):</div>
                <pre>{r.full_response}</pre>
                {r.competitors_mentioned?.length > 0 && (
                  <div className="response-competitors">
                    Competitors mentioned: {r.competitors_mentioned.join(', ')}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
