import React, { useState, useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useAuth } from '../AuthContext'
import { api } from '../api'
import { Radar, Package, Settings, CreditCard, LogOut, Rocket, Search, CheckCircle, XCircle, Loader } from 'lucide-react'
import ProductModal from '../components/ProductModal'
import ScanResults from '../components/ScanResults'
import './Dashboard.css'

export default function Dashboard() {
  const { user, logout } = useAuth()
  const [products, setProducts] = useState([])
  const [selectedProduct, setSelectedProduct] = useState(null)
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [scanMessage, setScanMessage] = useState('')
  const [searchParams] = useSearchParams()

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

  const triggerScan = async () => {
    if (!selectedProduct) return
    setScanning(true)
    setScanMessage('')
    try {
      await api.scanProduct(selectedProduct.id)
      setScanMessage('success:Scan started! Results will appear in a few minutes.')
    } catch (e) {
      setScanMessage(`error:${e.message}`)
    } finally {
      setScanning(false)
    }
  }

  const handleProductCreated = (product) => {
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
          <Radar size={16} />
          <span>Mention Tracker</span>
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

            {scanMessage && (
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

                <ScanResults productId={selectedProduct?.id} />
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
