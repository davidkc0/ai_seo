import React, { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Search, BarChart2, Mail, Zap, Target, Sparkles } from 'lucide-react'
import doughnut from '../assets/doughnut.jpg'
import cube from '../assets/cube.jpg'
import diamond from '../assets/diamond.jpg'
import illusionLogo from '../assets/illusion_logo.svg'
import './Landing.css'
import { track } from '../analytics'

const features = [
  { icon: <Search size={24} />, title: 'Multi-AI Query Monitoring', desc: 'We ask ChatGPT, Claude, Gemini, and Perplexity the category questions your customers are already typing.' },
  { icon: <BarChart2 size={24} />, title: 'Mention Analytics', desc: 'See if your product gets mentioned, at what rank, and with what sentiment — compared to competitors.' },
  { icon: <Sparkles size={24} />, title: 'AI-Generated Recommendations', desc: 'Every scan, Claude reads your results and the Google AI Overview to tell you exactly what to fix next.' },
  { icon: <Target size={24} />, title: 'Google AI Overview Tracking', desc: 'We scrape the Overview box for your primary query so you know whether Google is citing you — and who it cites instead.' },
  { icon: <Mail size={24} />, title: 'Weekly Email Digest', desc: 'A scannable summary in your inbox every Monday — mentions, wins, and the one thing to work on this week.' },
  { icon: <Zap size={24} />, title: 'Competitor Tracking', desc: 'See exactly which competitors AI recommends instead of you — and spot patterns you can act on.' },
]

const testimonials = [
  { name: 'Sarah K.', role: 'Founder @ InvoiceFlow', text: 'I had no idea Claude was recommending Stripe Billing over us. Within 2 weeks of seeing the data, we updated our messaging and our AI mentions doubled.' },
  { name: 'Marcus T.', role: 'Head of Growth @ TaskStack', text: 'This is the tool I wish existed 2 years ago. AI is the new Google — you need to know where you show up.' },
  { name: 'Priya M.', role: 'CEO @ DeskSync', text: 'The weekly digest lands in my inbox every Monday and tells me more about AI search visibility than anything else.' },
]

export default function Landing() {
  useEffect(() => { track.landingViewed() }, [])

  return (
    <div className="landing">
      {/* Nav */}
      <nav className="landing-nav">
        <div className="logo">
          <img src={illusionLogo} alt="Illusion" />
        </div>
        <div className="nav-links">
          <a href="#features">Features</a>
          <a href="#pricing">Pricing</a>
          <Link to="/login">Log in</Link>
          <Link to="/register" className="btn-primary-sm">Start free trial</Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="hero">
        <div className="hero-left">
          <div className="hero-badge">New: Google AI Overview tracking →</div>
          <h1>Does AI recommend<br /><span className="gradient-text">your product</span>?</h1>
          <p className="hero-sub">
            Your customers ask ChatGPT, Claude, Gemini, and Perplexity for tool recommendations.
            Illusion shows you exactly what those AIs say — and tells you how to get mentioned more.
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
        <h2>How it works</h2>
        <div className="steps">
          <div className="step">
            <div className="step-num">1</div>
            <h3>Add your product</h3>
            <p>Tell us your product name, category, keywords, and competitors. Takes 30 seconds.</p>
          </div>
          <div className="step-arrow">→</div>
          <div className="step">
            <div className="step-num">2</div>
            <h3>We query every major AI</h3>
            <p>Illusion asks Claude, ChatGPT, Gemini, and Perplexity the questions your customers are actually asking.</p>
          </div>
          <div className="step-arrow">→</div>
          <div className="step">
            <div className="step-num">3</div>
            <h3>Get your playbook</h3>
            <p>See your rankings, sentiment, and competitors — plus a Claude-written list of exactly what to do next.</p>
          </div>
        </div>
      </section>

      {/* Testimonials */}
      <section className="testimonials-section">
        <h2>Founders love it</h2>
        <div className="testimonials-grid">
          {testimonials.map(t => (
            <div key={t.name} className="testimonial-card">
              <p>"{t.text}"</p>
              <div className="testimonial-author">
                <strong>{t.name}</strong>
                <span>{t.role}</span>
              </div>
            </div>
          ))}
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
              <li>✓ AI-generated recommendations</li>
              <li>✓ Google AI Overview tracking</li>
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
              <li>✓ AI-generated recommendations</li>
              <li>✓ Google AI Overview tracking</li>
              <li>✓ Weekly email digest</li>
              <li>✓ Competitor comparison</li>
              <li>✓ Instant mention alerts</li>
            </ul>
            <Link to="/register" className="plan-btn">Get started →</Link>
          </div>
        </div>
      </section>

      {/* Footer CTA */}
      <section className="footer-cta">
        <h2>AI is the new search engine.</h2>
        <p>Millions of people ask AI what tools to use every day.<br />Make sure yours gets recommended.</p>
        <Link to="/register" className="cta-btn-primary">Start tracking for free →</Link>
      </section>

      <footer className="footer">
        <div>© 2026 Illusion</div>
        <div className="footer-links">
          <a href="#">Privacy</a>
          <a href="#">Terms</a>
          <Link to="/login">Log in</Link>
        </div>
      </footer>
    </div>
  )
}
