import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import posthog from 'posthog-js'
import App from './App'
import './index.css'

// ── PostHog init (cookieless — no cookie banner needed) ─────────
posthog.init('phc_u5DvvCpYTgmqsAqvKt3NP57FVcWT2A8ZE66i8dvNuqBD', {
  api_host: 'https://us.i.posthog.com',
  ui_host: 'https://us.posthog.com',
  persistence: 'memory',
  capture_pageview: true,
  capture_pageleave: true,
  autocapture: true,
  disable_external_dependency_loading: true,
  session_recording: {
    recordCrossOriginIframes: false,
  },
})

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
)
