import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import posthog from 'posthog-js'
import App from './App'
import './index.css'

// ── PostHog init (cookieless — no cookie banner needed) ─────────
const PH_KEY = import.meta.env.VITE_POSTHOG_KEY
const PH_HOST = import.meta.env.VITE_POSTHOG_HOST || 'https://us.i.posthog.com'

if (PH_KEY) {
  posthog.init(PH_KEY, {
    api_host: PH_HOST,
    persistence: 'memory',           // cookieless mode
    capture_pageview: true,           // auto pageview on route change
    capture_pageleave: true,          // track when users leave
    autocapture: true,                // auto-capture clicks, inputs, etc.
    session_recording: {
      recordCrossOriginIframes: false,
    },
  })
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
)
