import React, { useState } from 'react'
import {
  AlertCircle,
  BookOpen,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  DollarSign,
  ExternalLink,
  FileQuestion,
  FileText,
  GitCompare,
  Globe,
  Lock,
  MapPin,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { track } from '../analytics'
import './WebsiteAuditReport.css'

const SCORE_LABELS = [
  { key: 'overall', label: 'Overall' },
  { key: 'ux', label: 'User experience' },
  { key: 'seo', label: 'SEO / local' },
  { key: 'ai', label: 'AI search' },
]

const CATEGORY_LABELS = {
  user_experience: 'UX',
  seo: 'SEO',
  local_seo: 'Local SEO',
  structured_data: 'Schema',
  content: 'Content',
  ai_search: 'AI search',
  technical: 'Technical',
}

function scoreClass(value) {
  if (value >= 80) return 'good'
  if (value >= 60) return 'ok'
  return 'weak'
}

function severityIcon(severity) {
  if (severity === 'high') return <AlertCircle size={14} />
  return <CheckCircle size={14} />
}

function suggestionIcon(type) {
  const icons = {
    FAQ: FileQuestion,
    'Service page': FileText,
    'Location page': MapPin,
    'Trust proof': ShieldCheck,
    Comparison: GitCompare,
    Guide: BookOpen,
    'Pricing/process': DollarSign,
  }
  const Icon = icons[type] || BookOpen
  return <Icon size={18} />
}

export default function WebsiteAuditReport({
  audit,
  publicToken,
  publicMode = false,
  onClaim,
  claiming = false,
}) {
  const [expanded, setExpanded] = useState(0)
  const [expandedSuggestion, setExpandedSuggestion] = useState(null)

  if (!audit) return null

  const scores = audit.scores || {}
  const findings = audit.findings || []
  const topFindings = publicMode ? findings.slice(0, 8) : findings
  const contentSuggestions = audit.content_suggestions || []
  const visibleSuggestions = publicMode ? contentSuggestions.slice(0, 3) : contentSuggestions
  const hasLockedSuggestions = publicMode && contentSuggestions.length > 3

  const toggleFinding = (idx, finding) => {
    setExpanded(expanded === idx ? null : idx)
    if (expanded !== idx) {
      track.findingExpanded(finding.category, finding.severity)
    }
  }

  const toggleSuggestion = (idx, suggestion) => {
    setExpandedSuggestion(expandedSuggestion === idx ? null : idx)
    if (expandedSuggestion !== idx) {
      track.contentSuggestionClicked(suggestion.type, suggestion.priority)
    }
  }

  const handleContentCta = () => {
    track.contentSuggestionsCtaClicked()
    onClaim?.()
  }

  return (
    <div className="audit-report">
      <div className="audit-report-header">
        <div>
          <div className="audit-report-kicker"><Globe size={13} /> Website audit</div>
          <h2>{audit.domain || audit.normalized_url}</h2>
          {audit.normalized_url && (
            <a className="audit-report-url" href={audit.normalized_url} target="_blank" rel="noreferrer">
              {audit.normalized_url} <ExternalLink size={12} />
            </a>
          )}
        </div>
        {audit.status === 'completed' && (
          <div className={`audit-score-ring ${scoreClass(scores.overall || 0)}`}>
            <span>{scores.overall ?? '-'}</span>
            <small>/100</small>
          </div>
        )}
      </div>

      {audit.status === 'failed' && (
        <div className="audit-error">
          <AlertCircle size={16} />
          <span>{audit.error || 'The audit failed. Try another URL or rerun it later.'}</span>
        </div>
      )}

      {audit.status !== 'completed' && audit.status !== 'failed' && (
        <div className="audit-progress">
          <Sparkles size={16} className="spin-icon" />
          <div>
            <strong>{audit.status === 'running' ? 'Auditing the site...' : 'Audit queued...'}</strong>
            <span>Checking crawlability, local trust signals, schema, CTAs, and AI-search readiness.</span>
          </div>
        </div>
      )}

      {audit.status === 'completed' && (
        <>
          <div className="audit-score-grid">
            {SCORE_LABELS.map(item => (
              <div className="audit-score-card" key={item.key}>
                <span className={`audit-score-value ${scoreClass(scores[item.key] || 0)}`}>
                  {scores[item.key] ?? '-'}
                </span>
                <span className="audit-score-label">{item.label}</span>
              </div>
            ))}
          </div>

          {audit.executive_summary && (
            <div className="audit-summary">{audit.executive_summary}</div>
          )}

          {publicMode && (
            <div className="audit-claim-card">
              <div className="audit-claim-icon"><Lock size={18} /></div>
              <div>
                <strong>Save this audit and track improvements</strong>
                <p>Create a free Illusion account to keep this report, rerun it later, and connect it to AI mention tracking.</p>
              </div>
              <button className="btn-primary" onClick={onClaim} disabled={claiming || !publicToken}>
                {claiming ? 'Saving...' : 'Save audit'}
              </button>
            </div>
          )}

          <div className="audit-findings">
            <div className="audit-section-title">Prioritized fixes</div>
            {topFindings.map((finding, idx) => {
              const open = expanded === idx
              return (
                <button
                  type="button"
                  className={`audit-finding severity-${finding.severity || 'medium'} ${open ? 'open' : ''}`}
                  key={`${finding.title}-${idx}`}
                  onClick={() => toggleFinding(idx, finding)}
                >
                  <div className="audit-finding-top">
                    <span className="audit-finding-severity">
                      {severityIcon(finding.severity)}
                      {finding.severity || 'medium'}
                    </span>
                    <span className="audit-finding-category">
                      {CATEGORY_LABELS[finding.category] || finding.category || 'Website'}
                    </span>
                    <span className="audit-finding-title">{finding.title}</span>
                    <span className="audit-finding-chevron">
                      {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </span>
                  </div>
                  {open && (
                    <div className="audit-finding-body">
                      {finding.evidence && <p><strong>Evidence:</strong> {finding.evidence}</p>}
                      {finding.fix && <p><strong>Fix:</strong> {finding.fix}</p>}
                      {finding.expected_impact && <p><strong>Impact:</strong> {finding.expected_impact}</p>}
                      <div className="audit-finding-meta">Effort: {finding.effort || 'medium'}</div>
                      {finding.suggested_copy && (
                        <div className="audit-suggested-copy">{finding.suggested_copy}</div>
                      )}
                    </div>
                  )}
                </button>
              )
            })}
          </div>

          {contentSuggestions.length > 0 && (
            <div className="audit-content-suggestions">
              <div className="audit-section-heading">
                <div className="audit-section-title">Content suggestions</div>
                <p>Ideas based on the crawl findings, missing service/trust signals, and questions customers are likely to ask AI tools.</p>
              </div>
              <div className="audit-suggestion-list">
                {visibleSuggestions.map((suggestion, idx) => {
                  const open = expandedSuggestion === idx
                  return (
                    <button
                      type="button"
                      className={`audit-suggestion priority-${suggestion.priority || 'medium'} ${open ? 'open' : ''}`}
                      key={`${suggestion.title}-${idx}`}
                      onClick={() => toggleSuggestion(idx, suggestion)}
                    >
                      <div className="audit-suggestion-icon">{suggestionIcon(suggestion.type)}</div>
                      <div className="audit-suggestion-copy">
                        <div className="audit-suggestion-meta">
                          <span>{suggestion.type || 'Guide'}</span>
                          <span>{suggestion.priority || 'medium'} priority</span>
                          <span>{suggestion.effort || 'medium'} effort</span>
                        </div>
                        <strong>{suggestion.title}</strong>
                        {suggestion.description && <p>{suggestion.description}</p>}
                        {suggestion.target_question && (
                          <div className="audit-suggestion-question">{suggestion.target_question}</div>
                        )}
                        {open && suggestion.outline?.length > 0 && (
                          <ul className="audit-suggestion-outline">
                            {suggestion.outline.map((step, stepIdx) => (
                              <li key={`${step}-${stepIdx}`}>{step}</li>
                            ))}
                          </ul>
                        )}
                        {open && suggestion.source_finding && (
                          <div className="audit-suggestion-source">Related fix: {suggestion.source_finding}</div>
                        )}
                      </div>
                      <span className="audit-suggestion-chevron">
                        {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                      </span>
                    </button>
                  )
                })}
                {hasLockedSuggestions && (
                  <div className="audit-suggestion-locked">
                    <div className="audit-suggestion-locked-preview">
                      <div className="audit-suggestion-icon"><Lock size={18} /></div>
                      <div className="audit-suggestion-copy">
                        <div className="audit-suggestion-meta"><span>More ideas</span><span>saved report</span></div>
                        <strong>Unlock the rest of the content plan</strong>
                        <p>Save this audit to keep the report, rerun it later, and see the remaining content suggestions.</p>
                      </div>
                    </div>
                    <button className="btn-primary audit-suggestion-unlock" type="button" onClick={handleContentCta} disabled={claiming || !publicToken}>
                      {claiming ? 'Saving...' : 'Save audit to unlock more'}
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}

          {audit.crawled_pages?.length > 0 && (
            <div className="audit-pages">
              <div className="audit-section-title">Pages checked</div>
              {audit.crawled_pages.map(page => (
                <div className="audit-page-row" key={page.url}>
                  <span>{page.title || page.url}</span>
                  <small>{page.word_count || 0} words</small>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
