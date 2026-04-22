import React, { useState, useEffect } from 'react'
import { api } from '../api'
import { useAuth } from '../AuthContext'
import { Link } from 'react-router-dom'
import { Globe, RefreshCw, Unplug, Plus, Loader, Lock, ArrowUpRight, Bot, Search, GraduationCap } from 'lucide-react'
import './BotAnalytics.css'

const PLATFORM_COLORS = {
  openai: '#10a37f',
  anthropic: '#d4a574',
  perplexity: '#20b8cd',
  google: '#4285f4',
  meta: '#0084ff',
}

const PLATFORM_LABELS = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  perplexity: 'Perplexity',
  google: 'Google',
  meta: 'Meta',
}

const CATEGORY_ICONS = {
  training: GraduationCap,
  search: Search,
  user_agent: Bot,
}

const CATEGORY_LABELS = {
  training: 'Training',
  search: 'Search / Live',
  user_agent: 'User-Facing',
}

export default function BotAnalytics() {
  const { user } = useAuth()
  const [connections, setConnections] = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [showConnect, setShowConnect] = useState(false)
  const [connectToken, setConnectToken] = useState('')
  const [zones, setZones] = useState([])
  const [loadingZones, setLoadingZones] = useState(false)
  const [connectError, setConnectError] = useState('')
  const [days, setDays] = useState(30)

  const isPaid = user?.plan !== 'free'

  useEffect(() => {
    if (isPaid) {
      loadData()
    } else {
      setLoading(false)
    }
  }, [isPaid, days])

  const loadData = async () => {
    try {
      const [conns, sum] = await Promise.all([
        api.getBotConnections(),
        api.getBotSummary(days),
      ])
      setConnections(conns)
      setSummary(sum)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const handleLookupZones = async () => {
    if (!connectToken.trim()) return
    setLoadingZones(true)
    setConnectError('')
    try {
      const z = await api.getBotZones(connectToken)
      setZones(z)
    } catch (e) {
      setConnectError(e.message)
    } finally {
      setLoadingZones(false)
    }
  }

  const handleConnect = async (zone) => {
    setConnectError('')
    try {
      await api.connectCloudflare({
        api_token: connectToken,
        zone_id: zone.id,
        zone_name: zone.name,
      })
      setShowConnect(false)
      setConnectToken('')
      setZones([])
      // Do initial sync
      const conns = await api.getBotConnections()
      setConnections(conns)
      if (conns.length > 0) {
        setSyncing(true)
        await api.syncBotTraffic(conns[conns.length - 1].id, 30)
        await loadData()
        setSyncing(false)
      }
    } catch (e) {
      setConnectError(e.message)
    }
  }

  const handleSync = async (connId) => {
    setSyncing(true)
    try {
      await api.syncBotTraffic(connId, days)
      await loadData()
    } catch (e) {
      console.error(e)
    } finally {
      setSyncing(false)
    }
  }

  const handleDisconnect = async (connId) => {
    try {
      await api.disconnectCdn(connId)
      setConnections(c => c.filter(x => x.id !== connId))
      setSummary(null)
    } catch (e) {
      console.error(e)
    }
  }

  // ── Upgrade Gate ──────────────────────────────────────────────────
  if (!isPaid) {
    return (
      <div className="bot-upgrade-gate">
        <Lock size={32} />
        <h3>AI Bot Analytics</h3>
        <p>See which AI crawlers are visiting your website — GPTBot, ClaudeBot, PerplexityBot, and more. Understand which pages they read and how often.</p>
        <p className="bot-upgrade-sub">Available on Starter and Growth plans.</p>
        <Link to="/pricing" className="bot-upgrade-btn">Upgrade to unlock</Link>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="bot-loading">
        <Loader size={20} className="spin" />
        <span>Loading bot analytics...</span>
      </div>
    )
  }

  // ── No connections yet ────────────────────────────────────────────
  if (connections.length === 0 && !showConnect) {
    return (
      <div className="bot-empty">
        <Globe size={32} />
        <h3>Connect Your CDN</h3>
        <p>Link your Cloudflare account to see which AI bots are crawling your website, which pages they visit, and how often.</p>
        <button className="bot-connect-btn" onClick={() => setShowConnect(true)}>
          <Plus size={16} /> Connect Cloudflare
        </button>
      </div>
    )
  }

  // ── Connect flow ──────────────────────────────────────────────────
  if (showConnect) {
    return (
      <div className="bot-connect-flow">
        <h3>Connect Cloudflare</h3>
        <p className="bot-connect-desc">
          Create an API token at <a href="https://dash.cloudflare.com/profile/api-tokens" target="_blank" rel="noopener noreferrer">dash.cloudflare.com <ArrowUpRight size={12} /></a> with <strong>Zone:Read</strong> and <strong>Analytics:Read</strong> permissions.
        </p>

        <div className="bot-connect-input-row">
          <input
            type="password"
            placeholder="Paste your Cloudflare API token"
            value={connectToken}
            onChange={e => setConnectToken(e.target.value)}
            className="bot-input"
          />
          <button
            className="bot-connect-btn"
            onClick={handleLookupZones}
            disabled={loadingZones || !connectToken.trim()}
          >
            {loadingZones ? <Loader size={14} className="spin" /> : 'Find zones'}
          </button>
        </div>

        {connectError && <p className="bot-error">{connectError}</p>}

        {zones.length > 0 && (
          <div className="bot-zones-list">
            <p className="bot-zones-label">Select a zone to connect:</p>
            {zones.map(z => (
              <button key={z.id} className="bot-zone-item" onClick={() => handleConnect(z)}>
                <Globe size={14} />
                <span>{z.name}</span>
                <ArrowUpRight size={12} />
              </button>
            ))}
          </div>
        )}

        <button className="bot-cancel-btn" onClick={() => { setShowConnect(false); setZones([]); setConnectError(''); }}>
          Cancel
        </button>
      </div>
    )
  }

  // ── Dashboard ─────────────────────────────────────────────────────
  const maxRequests = summary?.by_platform?.length
    ? Math.max(...summary.by_platform.map(p => p.requests))
    : 1

  return (
    <div className="bot-dashboard">
      {/* Header */}
      <div className="bot-header">
        <div className="bot-header-left">
          <h3>AI Bot Traffic</h3>
          <div className="bot-period-tabs">
            {[7, 14, 30].map(d => (
              <button
                key={d}
                className={`bot-period-tab ${days === d ? 'active' : ''}`}
                onClick={() => setDays(d)}
              >
                {d}d
              </button>
            ))}
          </div>
        </div>
        <div className="bot-header-right">
          {connections.map(c => (
            <div key={c.id} className="bot-connection-tag">
              <Globe size={12} />
              <span>{c.zone_name}</span>
              <button
                className="bot-sync-btn"
                onClick={() => handleSync(c.id)}
                disabled={syncing}
                title="Sync now"
              >
                <RefreshCw size={12} className={syncing ? 'spin' : ''} />
              </button>
              <button
                className="bot-disconnect-btn"
                onClick={() => handleDisconnect(c.id)}
                title="Disconnect"
              >
                <Unplug size={12} />
              </button>
            </div>
          ))}
          <button className="bot-add-btn" onClick={() => setShowConnect(true)}>
            <Plus size={14} />
          </button>
        </div>
      </div>

      {/* Stats Row */}
      {summary && (
        <>
          <div className="bot-stats-row">
            <div className="bot-stat-card">
              <span className="bot-stat-label">Total Requests</span>
              <span className="bot-stat-value">{(summary.total_requests || 0).toLocaleString()}</span>
            </div>
            <div className="bot-stat-card">
              <span className="bot-stat-label">Platforms</span>
              <span className="bot-stat-value">{summary.by_platform?.length || 0}</span>
            </div>
            <div className="bot-stat-card">
              <span className="bot-stat-label">Bot Types</span>
              <span className="bot-stat-value">{summary.by_bot?.length || 0}</span>
            </div>
            <div className="bot-stat-card">
              <span className="bot-stat-label">Pages Crawled</span>
              <span className="bot-stat-value">{summary.top_pages?.length || 0}</span>
            </div>
          </div>

          {/* Platform Breakdown */}
          <div className="bot-section">
            <h4>By Platform</h4>
            <div className="bot-bar-chart">
              {summary.by_platform?.map(p => (
                <div key={p.platform} className="bot-bar-row">
                  <span className="bot-bar-label">{PLATFORM_LABELS[p.platform] || p.platform}</span>
                  <div className="bot-bar-track">
                    <div
                      className="bot-bar-fill"
                      style={{
                        width: `${(p.requests / maxRequests) * 100}%`,
                        background: PLATFORM_COLORS[p.platform] || 'var(--primary)',
                      }}
                    />
                  </div>
                  <span className="bot-bar-value">{p.requests.toLocaleString()}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Bot Breakdown */}
          <div className="bot-section">
            <h4>By Bot</h4>
            <div className="bot-table">
              <div className="bot-table-header">
                <span>Bot</span>
                <span>Platform</span>
                <span>Type</span>
                <span>Requests</span>
              </div>
              {summary.by_bot?.map((b, i) => {
                const CatIcon = CATEGORY_ICONS[b.category] || Bot
                return (
                  <div key={i} className="bot-table-row">
                    <span className="bot-table-name">
                      <span className="bot-dot" style={{ background: PLATFORM_COLORS[b.platform] || '#888' }} />
                      {b.bot_name}
                    </span>
                    <span>{PLATFORM_LABELS[b.platform] || b.platform}</span>
                    <span className="bot-category-badge">
                      <CatIcon size={11} />
                      {CATEGORY_LABELS[b.category] || b.category}
                    </span>
                    <span className="bot-table-count">{b.requests.toLocaleString()}</span>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Top Pages */}
          <div className="bot-section">
            <h4>Top Pages Crawled</h4>
            <div className="bot-table">
              <div className="bot-table-header">
                <span>Path</span>
                <span>Requests</span>
              </div>
              {summary.top_pages?.map((p, i) => (
                <div key={i} className="bot-table-row bot-table-two-col">
                  <span className="bot-path">{p.path}</span>
                  <span className="bot-table-count">{p.requests.toLocaleString()}</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {(!summary || summary.total_requests === 0) && (
        <div className="bot-no-data">
          <p>No bot traffic data yet. Hit the sync button to pull data from Cloudflare.</p>
        </div>
      )}
    </div>
  )
}
