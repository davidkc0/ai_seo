import React, { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Search, BarChart2, Zap, Sparkles, Globe, MessageSquareText, ScanSearch, ListChecks } from 'lucide-react'
import doughnut from '../assets/doughnut.jpg'
import cube from '../assets/cube.jpg'
import diamond from '../assets/diamond.png'
import illusionLogo from '../assets/illusion_logo.svg'
import SiteFooter from '../components/SiteFooter'
import './Landing.css'
import { track } from '../analytics'

const features = [
  { icon: <Search size={24} />, title: 'Multi-AI Query Monitoring', desc: 'We ask ChatGPT, Claude, Gemini, and Perplexity the category questions your customers are already typing.' },
  { icon: <BarChart2 size={24} />, title: 'Mention Analytics', desc: 'See if your product gets mentioned, at what rank, and with what sentiment — compared to competitors.' },
  { icon: <Zap size={24} />, title: 'Competitor Tracking', desc: 'See exactly which competitors AI recommends instead of you — and spot patterns you can act on.' },
  { icon: <Globe size={24} />, title: 'AI Bot Traffic Analysis', desc: 'Connect your CDN to see which AI crawlers visit your site, which pages they read, and how often — the data GA4 completely misses.' },
  { icon: <img src="/ai_overview.svg" alt="" width={24} height={24} />, title: 'Google AI Overview Tracking', desc: 'We scrape the Overview box for your primary query so you know whether Google is citing you — and who it cites instead.' },
  { icon: <Sparkles size={24} />, title: 'Smart Summary & Action Plan', desc: 'Every scan generates an AI-powered diagnosis of your visibility — strengths, gaps, and a prioritized list of exactly what to fix next.' },
]

export default function Landing() {
  useEffect(() => { track.landingViewed() }, [])

  return (
    <div className="landing">
      <a
        href="/blog/what-50-small-business-websites-get-wrong-about-ai-search"
        className="landing-announcement"
      >
        <span>New research</span>
        <strong>What 50 small business websites get wrong about AI search</strong>
        <span className="landing-announcement-action">Read the report →</span>
      </a>

      {/* Nav */}
      <nav className="landing-nav">
        <div className="logo">
          <img src={illusionLogo} alt="Illusion" />
        </div>
        <div className="nav-links">
          <a href="#features">Features</a>
          <Link to="/analyze">Free analyzer</Link>
          <a href="#pricing">Pricing</a>
          <a href="/blog">Blog</a>
          <Link to="/login">Log in</Link>
          <Link to="/register" className="btn-primary-sm">Start free trial</Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="hero">
        <div className="hero-left">
          <Link to="/analyze" className="hero-badge">New: Free AI website analyzer →</Link>
          <h1>Know where<br />you stand <span className="hero-serif">in</span><br /><span className="gradient-text">AI search.</span></h1>
          <p className="hero-sub">
            Your customers ask ChatGPT, Claude, Gemini, and Perplexity for recommendations.
            Illusion shows you exactly what those AIs say, audits your website, and tells you what to fix next.
          </p>
          <form className="hero-cta" onSubmit={e => { e.preventDefault(); const email = e.target.email.value; window.location.href = `/register?email=${encodeURIComponent(email)}`; }}>
            <div className="hero-input-group">
              <input type="email" name="email" placeholder="you@company.com" required className="hero-email-input" />
              <button type="submit" className="cta-btn-primary">Start free trial →</button>
            </div>
            <span className="cta-hint">7 days free · No credit card required</span>
          </form>
          {/* Hero demo card */}
          <div className="hero-demo">
            <div className="demo-label">Live example — "What are the best project management tools?"</div>
            <div className="demo-results">
              <div className="demo-result mentioned">
                <span className="demo-rank">#2</span>
                <span className="demo-name">YourProduct</span>
                <span className="badge badge-green">Mentioned ✓</span>
                <span className="demo-sent">Sentiment: Positive</span>
              </div>
              <div className="demo-result">
                <span className="demo-rank">#1</span>
                <span className="demo-name">Asana</span>
                <span className="badge badge-gray">Competitor</span>
              </div>
              <div className="demo-result">
                <span className="demo-rank">#3</span>
                <span className="demo-name">Monday.com</span>
                <span className="badge badge-gray">Competitor</span>
              </div>
            </div>
          </div>
        </div>
        <div className="hero-right">
          <img src={diamond} className="hero-shape" alt="" aria-hidden="true" />
        </div>
      </section>

      {/* Features */}
      <section className="features-section" id="features">
        <h2>Everything you need to own AI search</h2>
        <p className="section-sub">Stop guessing. Start tracking.</p>
        <div className="features-grid">
          {features.map(f => (
            <div key={f.title} className="feature-card">
              <div className="feature-icon">{f.icon}</div>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="how-section">
        <div className="how-inner">
          <div className="how-heading">
            <span>How it works</span>
            <h2>One useful loop,<br />not another dashboard.</h2>
            <p>Start with the questions customers ask. See the answers they get. Fix what keeps your business out of them.</p>
          </div>
          <div className="steps">
            <article className="step">
              <div className="step-topline">
                <span className="step-num">01</span>
                <MessageSquareText size={20} aria-hidden="true" />
              </div>
              <h3>Set the questions</h3>
              <p>Add your business and the buying questions people ask before choosing a product or service like yours.</p>
            </article>
            <article className="step">
              <div className="step-topline">
                <span className="step-num">02</span>
                <ScanSearch size={20} aria-hidden="true" />
              </div>
              <h3>See the real answers</h3>
              <p>Illusion checks ChatGPT, Claude, Gemini, and Perplexity, then shows who gets mentioned and why.</p>
            </article>
            <article className="step">
              <div className="step-topline">
                <span className="step-num">03</span>
                <ListChecks size={20} aria-hidden="true" />
              </div>
              <h3>Make the next move</h3>
              <p>Use the audit, competitor patterns, and prioritized recommendations to fix the gaps that matter first.</p>
            </article>
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section className="pricing-section" id="pricing">
        <h2>Simple, transparent pricing</h2>
        <p className="section-sub">Start free. Upgrade when you need more.</p>
        <div className="pricing-grid">
          <div className="pricing-card">
            <div className="plan-name">Free Trial</div>
            <div className="plan-price">$0 <span>/7 days</span></div>
            <ul>
              <li>✓ 1 product</li>
              <li>✓ 3 keywords</li>
              <li>✓ Weekly AI scan</li>
              <li>✓ Basic dashboard</li>
              <li>✗ Email digest</li>
            </ul>
            <Link to="/register" className="plan-btn">Start free →</Link>
          </div>
          <div className="pricing-card popular">
            <div className="popular-badge">Most Popular</div>
            <div className="plan-name">Starter</div>
            <div className="plan-price">$19 <span>/month</span></div>
            <ul>
              <li>✓ 1 product</li>
              <li>✓ 5 keywords</li>
              <li>✓ Daily AI scan</li>
              <li>✓ Smart Summary & action plan</li>
              <li>✓ Google AI Overview tracking</li>
              <li>✓ AI bot traffic analysis</li>
              <li>✓ Weekly email digest</li>
              <li>✓ Competitor tracking</li>
            </ul>
            <Link to="/register" className="plan-btn plan-btn-primary">Get started →</Link>
          </div>
          <div className="pricing-card">
            <div className="plan-name">Growth</div>
            <div className="plan-price">$39 <span>/month</span></div>
            <ul>
              <li>✓ 3 products</li>
              <li>✓ 20 keywords</li>
              <li>✓ Daily AI scan</li>
              <li>✓ Smart Summary & action plan</li>
              <li>✓ Google AI Overview tracking</li>
              <li>✓ AI bot traffic analysis</li>
              <li>✓ Weekly email digest</li>
              <li>✓ Competitor comparison</li>
              <li>✓ Instant mention alerts</li>
            </ul>
            <Link to="/register" className="plan-btn">Get started →</Link>
          </div>
        </div>
        <div className="landing-hands-on">
          <div className="landing-hands-on-heading">
            <span>Need hands-on help?</span>
            <h3>Get the data, or get the fixes handled.</h3>
            <p>Start with the free audit so every recommendation is based on your actual website.</p>
          </div>
          <div className="landing-service">
            <strong>$49 founder visibility review</strong>
            <p>Review the audit, run your first AI visibility scan, and leave with the three highest-priority actions.</p>
            <Link to="/analyze">Run the audit first →</Link>
          </div>
          <div className="landing-service">
            <strong>Flat-fee website cleanup</strong>
            <p>Have Illusion handle the recommended clarity, schema, service-page, trust, and CTA fixes.</p>
            <a
              href="mailto:david@illusion.ai?subject=Flat-fee%20website%20cleanup"
              onClick={() => track.websiteCleanupRequested()}
            >
              Request a quote →
            </a>
          </div>
        </div>
      </section>

      {/* Footer CTA */}
      <section className="footer-cta">
        <div className="footer-cta-grid" />
        <div className="footer-cta-glow" />
        <div className="footer-cta-glow footer-cta-glow-left" />
        <div className="footer-cta-wrap">
          <div className="footer-cta-box">
            <h2>
              Find out where you stand <span className="footer-cta-serif">in</span>{' '}
              <span className="footer-cta-em">AI search</span> — in 60 seconds.
            </h2>
            <div className="footer-cta-action">
              <Link to="/register" className="cta-btn-primary">Start free trial →</Link>
              <span>7 days free · no credit card</span>
            </div>
          </div>
        </div>
      </section>

      <SiteFooter />
    </div>
  )
}
