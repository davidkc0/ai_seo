import React, { useState, useEffect, useRef } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useAuth } from '../AuthContext'
import { api } from '../api'
import { Package, Settings, CreditCard, LogOut, Rocket, Search, CheckCircle, XCircle, Loader } from 'lucide-react'
import ProductModal from '../components/ProductModal'
import ScanResults from '../components/ScanResults'
import Recommendations from '../components/Recommendations'
import illusionLogo from '../assets/illusion_logo.svg'
import { track } from '../analytics'
import './Dashboard.css'

const RESEARCH_MESSAGES = [
  'Asking Claude...',
  'Asking GPT...',
  'Asking Gemini...',
  'Asking Perplexity...',
  'Parsing responses...',
  'Tallying mentions...',
]

export default function Dashboard() {
  const { user, logout } = useAuth()
  const [products, setProducts] = useState([])
  const [selectedProduct, setSelectedProduct] = useState(null)
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [scanStatus, setScanStatus] = useState('')
  const [scanMessage, setScanMessage] = useState('')
  const [resultsRefreshKey, setResultsRefreshKey] = useState(0)
  const [searchParams] = useSearchParams()

  const pollRef = useRef(null)
  const statusRotateRef = useRef(null)

  useEffect(() => {
    loadProducts()
    if (searchParams.get('upgraded') === 'true') {
      setScanMessage('Plan upgraded successfully! Your new limits are now active.')
    }
  }, [])

  useEffect(() => {
    if (selectedProduct) {
      loadSummary(selectedProduct.id)
    }
  }, [selectedProduct])

  // Cleanup pollers on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
      if (statusRotateRef.current) clearInterval(statusRotateRef.current)
    }
  }, [])

  const loadProducts = async () => {
    try {
      const data = await api.getProducts()
      setProducts(data)
      if (data.length > 0) setSelectedProduct(data[0])
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const loadSummary = async (productId) => {
    try {
      const data = await api.getSummary(productId)
      setSummary(data)
    } catch (e) {
      console.error(e)
    }
  }

  const stopScanning = (msg) => {
    if (pollRef.current) clearInterval(pollRef.current)
    if (statusRotateRef.current) clearInterval(statusRotateRef.current)
    pollRef.current = null
    statusRotateRef.current = null
    setScanning(false)
    setScanStatus('')
    if (msg) setScanMessage(msg)
  }

  const triggerScan = async () => {
    if (!selectedProduct) return

    // Capture the newest existing result ID so we can detect new ones
    let baselineId = 0
    try {
      const existing = await api.getResults(selectedProduct.id, 1)
      baselineId = existing[0]?.id ?? 0
    } catch {}

    const scanStartTime = Date.now()
    setScanning(true)
    setScanMessage('')
    setScanStatus(RESEARCH_MESSAGES[0])

    try {
      await api.scanProduct(selectedProduct.id)
      track.scanRun()
    } catch (e) {
      setScanning(false)
      setScanStatus('')
      setScanMessage(`error:${e.message}`)
      return
    }

    // Rotate the "what we're doing right now" message
    let msgIdx = 0
    statusRotateRef.current = setInterval(() => {
      msgIdx = (msgIdx + 1) % RESEARCH_MESSAGES.length
      setScanStatus(RESEARCH_MESSAGES[msgIdx])
    }, 2500)

    // Poll for new results
    const POLL_INTERVAL_MS = 4000
    const TIMEOUT_MS = 4 * 60 * 1000
    const IDLE_POLLS_TO_STOP = 4 // ~16s of no new results after at least one arrived
    const productId = selectedProduct.id
    let lastSeenId = baselineId
    let idlePolls = 0

    pollRef.current = setInterval(async () => {
      if (Date.now() - scanStartTime > TIMEOUT_MS) {
        stopScanning('error:Scan timed out. Some results may still arrive — try refreshing.')
        return
      }

      try {
        const latest = await api.getResults(productId, 20)
        const topId = latest[0]?.id ?? 0
        if (topId !== lastSeenId && topId > baselineId) {
          lastSeenId = topId
          idlePolls = 0
          // Refresh summary + trigger ScanResults reload
          loadSummary(productId)
          setResultsRefreshKey(k => k + 1)
        } else if (topId > baselineId) {
          idlePolls += 1
          if (idlePolls >= IDLE_POLLS_TO_STOP) {
            loadSummary(productId)
            setResultsRefreshKey(k => k + 1)
            stopScanning('success:Scan complete.')
            // Track completion with mention rate
            try {
              const s = await api.getSummary(productId)
              if (s) track.scanCompleted(s.mention_rate)
            } catch {}
          }
        }
      } catch (e) {
        console.error(e)
      }
    }, POLL_INTERVAL_MS)
  }

  const handleProductCreated = (product) => {
    track.firstProductAdded()
    setProducts(prev => [...prev, product])
    setSelectedProduct(product)
    setShowModal(false)
  }

  const mentionRate = summary ? Math.round((summary.mention_rate || 0) * 100) : 0
  const mentionColor = mentionRate >= 70 ? '#22c55e' : mentionRate >= 40 ? '#f59e0b' : '#6b7280'

  if (loading) return <div className="spinner" />

  const scanMsgType = scanMessage.startsWith('error:') ? 'error' : 'success'
  const scanMsgText = scanMessage.replace(/^(error|success):/, '')

  return (
    <div className="dashboard">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <img src={illusionLogo} alt="Illusion" />
        </div>

        <div className="sidebar-section">
          <div className="sidebar-label">Products</div>
          {products.map(p => (
            <button
              key={p.id}
              className={`sidebar-item ${selectedProduct?.id === p.id ? 'active' : ''}`}
              onClick={() => setSelectedProduct(p)}
            >
              <Package size={14} className="sidebar-item-icon" />
              <span>{p.name}</span>
            </button>
          ))}
          <button className="sidebar-item add-product" onClick={() => setShowModal(true)}>
            <span>+ Add product</span>
          </button>
        </div>

        <div className="sidebar-nav">
          <Link to="/settings" className="sidebar-item">
            <Settings size={14} className="sidebar-item-icon" />
            Settings
          </Link>
          <Link to="/pricing" className="sidebar-item">
            <CreditCard size={14} className="sidebar-item-icon" />
            Upgrade
          </Link>
          <button className="sidebar-item" onClick={logout}>
            <LogOut size={14} className="sidebar-item-icon" />
            Log out
          </button>
        </div>

        <div className="plan-badge">
          Plan: <strong>{user?.plan || 'free'}</strong>
        </div>
      </aside>

      {/* Main content */}
      <main className="main-content">
        {!selectedProduct && products.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon"><Rocket size={48} strokeWidth={1.5} /></div>
            <h2>Add your first product</h2>
            <p>Tell us about your SaaS product and we'll start tracking what AI says about it.</p>
            <button className="btn-primary" onClick={() => setShowModal(true)}>
              + Add product
            </button>
          </div>
        ) : (
          <>
            {/* Header */}
            <div className="content-header">
              <div>
                <h1>{selectedProduct?.name}</h1>
                <span className="category-tag">{selectedProduct?.category}</span>
              </div>
              <button
                className="btn-primary scan-btn"
                onClick={triggerScan}
                disabled={scanning}
              >
                {scanning ? (
                  <><Loader size={14} className="spin-icon" /> Scanning...</>
                ) : (
                  <><Search size={14} /> Run scan now</>
                )}
              </button>
            </div>

            {scanning && (
              <div className="researching-banner">
                <Loader size={18} className="spin-icon" />
                <div className="researching-text">
                  <div className="researching-title">Researching across 4 AI providers</div>
                  <div className="researching-sub">{scanStatus || 'Starting scan...'}</div>
                </div>
                <div className="researching-hint">
                  Results will appear below as they come in · ~60–90s total
                </div>
              </div>
            )}

            {!scanning && scanMessage && (
              <div className={scanMsgType === 'error' ? 'error-msg' : 'success-msg'}>
                {scanMsgText}
              </div>
            )}

            {summary ? (
              <>
                {/* Stats */}
                <div className="stats-grid">
                  <div className="stat-card">
                    <div className="stat-value" style={{ color: mentionColor }}>{mentionRate}%</div>
                    <div className="stat-label">Mention rate</div>
                    <div className="stat-sub">{summary.mentions}/{summary.total_queries} queries</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-value">
                      {summary.best_position ? `#${summary.best_position}` : '—'}
                    </div>
                    <div className="stat-label">Best ranking</div>
                    <div className="stat-sub">across all queries</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-value">
                      {Object.entries(summary.sentiment_breakdown || {})
                        .sort((a, b) => b[1] - a[1])[0]?.[0] || '—'}
                    </div>
                    <div className="stat-label">Top sentiment</div>
                    <div className="stat-sub">of mentions</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-value">{summary.competitors_seen?.length || 0}</div>
                    <div className="stat-label">Competitors seen</div>
                    <div className="stat-sub">in same responses</div>
                  </div>
                </div>

                {/* Recommendations (Claude-generated) */}
                <Recommendations
                  productId={selectedProduct?.id}
                  refreshKey={resultsRefreshKey}
                  scanning={scanning}
                />

                {/* Competitors */}
                {summary.competitors_seen?.length > 0 && (
                  <div className="card" style={{ marginBottom: 24 }}>
                    <h3>Competitors mentioned alongside</h3>
                    <div className="competitor-list">
                      {summary.competitors_seen.map(c => (
                        <span key={c} className="competitor-tag">{c}</span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Recent scans */}
                <div className="card">
                  <div className="card-header">
                    <h3>Recent AI responses</h3>
                    <span className="card-hint">Last {summary.recent_scans?.length} queries</span>
                  </div>
                  <div className="scan-list">
                    {summary.recent_scans?.map((scan, i) => (
                      <div key={i} className="scan-row">
                        <div className={`scan-dot ${scan.mentioned ? 'green' : 'gray'}`} />
                        <div className="scan-info">
                          <div className="scan-query">"{scan.query}"</div>
                          <div className="scan-meta">
                            {scan.mentioned ? (
                              <>
                                <span className="badge badge-green">Mentioned</span>
                                {scan.position && <span>#{scan.position}</span>}
                                {scan.sentiment && <span>{scan.sentiment}</span>}
                              </>
                            ) : (
                              <span className="badge badge-gray">Not mentioned</span>
                            )}
                            <span className="scan-date">
                              {scan.created_at ? new Date(scan.created_at).toLocaleDateString() : ''}
                            </span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <ScanResults productId={selectedProduct?.id} refreshKey={resultsRefreshKey} />
              </>
            ) : (
              <div className="empty-state">
                <div className="empty-icon"><Search size={48} strokeWidth={1.5} /></div>
                <h2>No scans yet</h2>
                <p>Click "Run scan now" to see what AI says about {selectedProduct?.name}.</p>
              </div>
            )}
          </>
        )}
      </main>

      {showModal && (
        <ProductModal
          onClose={() => setShowModal(false)}
          onCreated={handleProductCreated}
          plan={user?.plan}
        />
      )}
    </div>
  )
}
