/**
 * PostHog event helpers — typed wrappers so event names stay consistent.
 *
 * Usage:  import { track } from '../analytics'
 *         track.scanRun()
 *
 * PostHog is initialised in main.jsx.  If PostHog isn't loaded (e.g. in dev
 * without a key) every call here is a safe no-op.
 */
import posthog from 'posthog-js'

function capture(event, properties) {
  try {
    posthog.capture(event, properties)
  } catch {
    // PostHog not initialised — silent no-op in dev
  }
}

export const track = {
  // ── Landing / top of funnel ───────────────────────────────────
  landingViewed: () => capture('landing_viewed'),
  pricingViewed: () => capture('pricing_viewed'),

  // ── Auth ──────────────────────────────────────────────────────
  registerStarted: () => capture('register_started'),
  registerCompleted: (segment) => capture('register_completed', { segment }),
  registerFailed: (reason) => capture('register_failed', { reason }),
  loginCompleted: () => capture('login_completed'),

  // ── Core product ──────────────────────────────────────────────
  firstProductAdded: () => capture('first_product_added'),
  firstScanRun: () => capture('first_scan_run'),
  scanRun: () => capture('scan_run'),
  scanCompleted: (mentionRate) =>
    capture('scan_completed', { mention_rate: mentionRate }),
  recommendationViewed: () => capture('recommendation_viewed'),

  // ── Website audit ───────────────────────────────────────────
  auditStarted: (source) => capture('website_audit_started', { source }),
  auditCompleted: (score) => capture('website_audit_completed', { score }),
  auditClaimed: () => capture('website_audit_claimed'),
  auditRerun: () => capture('website_audit_rerun'),
  findingExpanded: (category, severity) =>
    capture('website_audit_finding_expanded', { category, severity }),
  signupFromAudit: () => capture('signup_from_audit'),

  // ── Monetisation ──────────────────────────────────────────────
  checkoutStarted: (plan) => capture('checkout_started', { plan }),
  checkoutCompleted: (plan) => capture('checkout_completed', { plan }),

  // ── Email → product bridge ────────────────────────────────────
  unsubscribeClicked: () => capture('unsubscribe_clicked'),
}
