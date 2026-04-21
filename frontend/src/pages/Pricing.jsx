import React, { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../AuthContext'
import { api } from '../api'
import { CheckCircle, Lightbulb } from 'lucide-react'
import './Pricing.css'
import { track } from '../analytics'

export default function Pricing() {
  const { user } = useAuth()
  const [plans, setPlans] = useState([])
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    api.getPlans().then(d => setPlans(d.plans)).catch(console.error)
    track.pricingViewed()
  }, [])

  const subscribe = async (planId) => {
    if (!user) {
      navigate('/register')
      return
    }
    if (planId === 'free') {
      navigate('/dashboard')
      return
    }
    setLoading(true)
    try {
      const { checkout_url } = await api.createCheckout(planId)
      track.checkoutStarted(planId)
      window.location.href = checkout_url
    } catch (e) {
      alert(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="pricing-page">
      <Link to="/" className="pricing-back">← Back</Link>

      <div className="pricing-page-header">
        <h1>Simple pricing</h1>
        <p>Start free. No credit card required for trial.</p>
        <div className="pricing-annual-note">
          <Lightbulb size={14} /> Annual plans save 2 months — coming soon
        </div>
      </div>

      <div className="pricing-page-grid">
        {plans.map(plan => (
          <div
            key={plan.id}
            className={`pricing-page-card ${plan.popular ? 'popular' : ''}`}
          >
            {plan.popular && (
              <div className="popular-badge">Most Popular</div>
            )}
            <div className="plan-name">{plan.name}</div>
            <div className="plan-price">
              {plan.price === 0 ? 'Free' : `$${plan.price}`}
              {plan.price > 0 && <span>/mo</span>}
            </div>
            <ul className="plan-features">
              {plan.features.map(f => (
                <li key={f}>
                  <CheckCircle size={14} className="feature-check" />
                  {f}
                </li>
              ))}
            </ul>
            <button
              onClick={() => subscribe(plan.id)}
              disabled={loading || (user && user.plan === plan.id)}
              className={`plan-page-btn ${plan.popular ? 'plan-page-btn-primary' : ''}`}
            >
              {user && user.plan === plan.id
                ? 'Current plan'
                : plan.price === 0 ? 'Start free →' : 'Get started →'}
            </button>
          </div>
        ))}
      </div>

      <div className="pricing-faq">
        <div className="faq-item">
          <div className="faq-q">Can I cancel anytime?</div>
          <div className="faq-a">Yes. Cancel before your billing date and you won't be charged again.</div>
        </div>
        <div className="faq-item">
          <div className="faq-q">What happens after the trial?</div>
          <div className="faq-a">Your account stays active. You'll just need to upgrade to keep scanning.</div>
        </div>
        <div className="faq-item">
          <div className="faq-q">Which AIs do you track?</div>
          <div className="faq-a">ChatGPT, Claude, Gemini, and Perplexity. More coming soon.</div>
        </div>
      </div>
    </div>
  )
}
