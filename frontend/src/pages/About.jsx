import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { Linkedin, ChevronDown } from 'lucide-react'
import Seo from '../components/Seo'
import SiteFooter from '../components/SiteFooter'
import illusionLogo from '../assets/illusion_logo.svg'
import './About.css'

export default function About() {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="about-page">
      <Seo
        title="About Illusion - Affordable AI Search Visibility"
        description="Meet Illusion, the bootstrapped AI search visibility product built for startups, founders, and small businesses."
        path="/about"
      />

      <nav className="about-nav">
        <Link to="/" className="about-logo" aria-label="Illusion home">
          <img src={illusionLogo} alt="Illusion" />
        </Link>
        <div className="about-nav-links">
          <Link to="/analyze">Free analyzer</Link>
          <Link to="/pricing">Pricing</Link>
          <a href="/blog">Blog</a>
          <Link to="/login">Log in</Link>
          <Link to="/register" className="btn-primary-sm">Start free trial</Link>
        </div>
      </nav>

      <main>
        <section className="about-hero">
          <h1>
            The Team
            <span>Behind Illusion</span>
          </h1>
          <p>
            Built for founders, startups, and small businesses that want to know
            whether AI answer engines understand and recommend them before paying
            enterprise prices for a dashboard full of vibes.
          </p>
        </section>

        <section className="about-quote-section">
          <div className="about-quote-card">
            <blockquote>
              "It would be kind of weird to quote myself like this, but yeah,
              AI is changing how people discover brands, and small businesses
              deserve a product that they do not have to pay an arm and a leg
              for to have the tools to see, act, and win on AI Search."
            </blockquote>
            <cite>David Ciaffoni, CEO</cite>
          </div>
        </section>

        <section className="about-section">
          <div className="about-section-heading">
            <h2>Our Team</h2>
            <p>One founder. Plenty of opinions.</p>
          </div>

          <div className="about-team-grid">
            <article className={`about-person-card ${expanded ? 'expanded' : ''}`}>
              <div className="about-person-image-wrap">
                <img src="/profile_pic.jpg" alt="David Ciaffoni" />
              </div>
              <div className="about-person-body">
                <div className="about-person-topline">
                  <div>
                    <h3>David Ciaffoni</h3>
                    <p>CEO</p>
                  </div>
                  <a
                    href="https://www.linkedin.com/in/david-ciaffoni/"
                    target="_blank"
                    rel="noreferrer"
                    className="about-social-link"
                    aria-label="David Ciaffoni on LinkedIn"
                  >
                    <Linkedin size={18} />
                  </a>
                </div>
                <p className="about-person-summary">
                  Founder of Illusion. Previously founding designer at Lime and
                  Head of Product at Favorited.
                </p>

                {expanded && (
                  <div className="about-person-more">
                    <p>
                      Before Illusion, David worked across product, design, and
                      growth for consumer and startup products. Illusion is the
                      result of being annoyed enough by overpriced AI SEO tools
                      to build the useful version.
                    </p>
                  </div>
                )}

                <button
                  type="button"
                  className="about-read-more"
                  onClick={() => setExpanded(current => !current)}
                  aria-expanded={expanded}
                >
                  {expanded ? 'Close' : 'read more'}
                  <ChevronDown size={16} />
                </button>
              </div>
            </article>
          </div>
        </section>

        <section className="about-section about-investors">
          <div className="about-section-heading">
            <h2>Our Investors</h2>
            <p>
              We are grateful for never having taken VC money and, frankly,
              something like this does not really need VC money. We definitely
              would not take any money from YC anyway.
            </p>
          </div>
        </section>

        <section className="about-section about-advisors">
          <div className="about-section-heading">
            <h2>Our Advisors</h2>
            <p>We are fortunate to be guided by the following thought leaders.</p>
          </div>

          <div className="about-advisor-grid">
            <article className="about-advisor-card">
              <div className="about-advisor-image-wrap">
                <img src="/mickey.png" alt="Mickey" />
              </div>
              <h3>Mickey</h3>
              <p>Feline eunuch advisor</p>
            </article>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  )
}
