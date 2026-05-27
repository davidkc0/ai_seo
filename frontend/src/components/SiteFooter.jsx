import React from 'react'
import illusionLogo from '../assets/illusion_logo.svg'
import { track } from '../analytics'
import './SiteFooter.css'

const footerResources = [
  { title: 'Free AI Website Analyzer', href: '/ai-website-analyzer' },
  { title: 'Best AI Search Monitoring Tools', href: '/blog/best-ai-search-monitoring-tools' },
  { title: 'Generative Engine Optimization Guide', href: '/blog/generative-engine-optimization-guide' },
  { title: 'Profound vs Illusion', href: '/blog/profound-vs-illusion' },
  { title: 'AthenaHQ vs Illusion', href: '/blog/athenahq-vs-illusion' },
  { title: 'Improve Your Website for AI Search', href: '/blog/improve-website-for-ai-search' },
  { title: 'Small Business AI Search Study', href: '/blog/what-50-small-business-websites-get-wrong-about-ai-search' },
]

export default function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="site-footer-main">
        <div className="site-footer-brand">
          <img src={illusionLogo} alt="Illusion" />
          <p>Affordable AI search visibility for founders, startups, and small businesses.</p>
        </div>

        <div className="site-footer-column">
          <h3>Get in Touch</h3>
          <a href="mailto:hello@illusion.ai">Contact Us</a>
        </div>

        <div className="site-footer-column">
          <h3>Socials</h3>
          <a href="https://x.com/TryIllusionAI" target="_blank" rel="noreferrer">X.com</a>
          <a href="/blog">Blog</a>
        </div>

        <div className="site-footer-column">
          <h3>Company</h3>
          <a href="/about">About Us</a>
          <a href="/blog">Case Studies</a>
          <a href="/login">Login</a>
        </div>

        <div className="site-footer-column site-footer-resources">
          <h3>Resources</h3>
          {footerResources.map(resource => (
            <a
              key={resource.title}
              href={resource.href}
              onClick={() => track.resourceClicked(resource.title)}
            >
              {resource.title}
            </a>
          ))}
        </div>

        <div className="site-footer-column">
          <h3>Legal</h3>
          <a href="/terms">Terms</a>
          <a href="/privacy">Privacy</a>
        </div>
      </div>

      <div className="site-footer-bottom">
        <span>Copyright 2026 Illusion.ai</span>
        <span>Created in Santa Monica</span>
      </div>
    </footer>
  )
}
