# Blog + SEO Plan

Working plan for the Illusion blog and the one-time SEO cleanup work that
goes with it. Modeled on [Profound's playbook](https://www.tryprofound.com/blog) —
ship comparison-heavy content that intercepts buyer-intent queries
("AthenaHQ vs Profound", etc.), paired with generative-engine-optimization
(GEO) thought-leadership posts that build topical authority.

Last updated: 2026-04-21

---

## The goal

Two distinct SEO wins, each with its own path:

1. **Conquesting**: rank on page 1 of Google for "X vs Illusion" and
   "Illusion vs X" for every competitor. These queries are tiny in volume but
   every click is a late-funnel, comparison-stage buyer. Profound's review of
   AthenaHQ is the canonical example — ranking #1 for a competitor's
   brand-plus-comparison query converts like nothing else.
2. **Category authority**: own the phrase *generative engine optimization* and
   its adjacent queries ("rank in ChatGPT", "Google AI Overview SEO", etc.).
   This is a net-new category — whoever publishes the clearest guide first
   becomes the default citation. Profound is aiming here too.

Secondary: every post doubles as raw material for the marketing email agent
(Part 3 of the email plan).

---

## The Profound playbook, reverse-engineered

Looking at what makes <https://www.tryprofound.com/blog/athenahq-review-not-the-best-for-enterprises>
work, there are ~6 patterns we should copy wholesale:

1. **Honest-but-sharp angle.** Not a hit piece, but not neutral either. They
   call out AthenaHQ's weaknesses where they exist and admit where it's
   competitive. That nuance is why the post doesn't read as spam and why
   it ranks.
2. **Slug targets the exact query.** `/blog/athenahq-review-not-the-best-for-enterprises`
   — Google sees "athenahq review" right in the URL.
3. **H1 = headline. Title tag slightly different and keyword-rich.**
4. **First 100 words repeat the target keyword verbatim.** Old-school on-page
   SEO still pays.
5. **Comparison table** near the top. Google loves tables; sometimes pulls
   them into AI Overviews directly.
6. **"Alternatives to X" block at the bottom** with internal links to 3–5
   other competitor reviews. Compounds internal link equity.

Illusion has one edge Profound doesn't: **we can show primary research inside
every post.** Screenshot Claude's actual answer when asked "what's the best
AI search tracking tool" and paste it in. No competitor can fake that.

---

## TL;DR build order

| # | Step | Effort |
|---|---|---|
| 1 | **SEO baseline cleanup** (meta tags, OG, sitemap, GSC) | ½ day |
| 2 | **Blog infrastructure** — Astro `/blog` in the same repo | ½ day |
| 3 | **First 5 posts** (3 comparison + 2 GEO pillars) | 1 week |
| 4 | **Programmatic comparison pages** templated | 1–2 days |
| 5 | **Off-page work** — GSC submission, directories, backlinks | ongoing |
| 6 | **Wire analytics** — PostHog funnel blog → signup | ½ day |

Steps 1 and 2 block everything else. The other four can happen in parallel
once the blog is live.

---

## Step 1 — SEO baseline cleanup (no-brainer hacks)

Every minute spent here has a higher ROI than any blog post for the first
couple of weeks. The current `frontend/index.html` is extremely bare — a dozen
easy wins in one file.

### What's missing right now
- No `<meta name="description">` — Google generates a description from
  body text, and it's always worse than one we write.
- No Open Graph tags → link previews in Twitter/LinkedIn/Slack/iMessage
  render as "Illusion" with no image. Catastrophic for sharing.
- No `<link rel="canonical">` → once marketing UTM params start flying
  around we'll have duplicate-content issues.
- No `sitemap.xml` or `robots.txt` → Google has to discover every page on
  its own.
- No JSON-LD structured data → we miss out on rich snippets.

### Fixes

In `frontend/index.html`, add:

```html
<meta name="description" content="Illusion tracks what Claude, ChatGPT, Gemini and Perplexity say about your product. See where you rank in AI search results and what to fix — in 60 seconds.">
<link rel="canonical" href="https://illusion.ai/">

<!-- Open Graph -->
<meta property="og:title" content="Illusion — Know Where You Stand in AI Search">
<meta property="og:description" content="Track how Claude, ChatGPT, Gemini and Perplexity answer questions about your product.">
<meta property="og:image" content="https://illusion.ai/og-image.png">
<meta property="og:url" content="https://illusion.ai/">
<meta property="og:type" content="website">

<!-- Twitter -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Illusion — Know Where You Stand in AI Search">
<meta name="twitter:description" content="Track how Claude, ChatGPT, Gemini and Perplexity answer questions about your product.">
<meta name="twitter:image" content="https://illusion.ai/og-image.png">

<!-- JSON-LD: SoftwareApplication -->
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "Illusion",
  "applicationCategory": "BusinessApplication",
  "operatingSystem": "Web",
  "offers": { "@type": "Offer", "price": "19", "priceCurrency": "USD" }
}
</script>
```

Then:

- Create `frontend/public/og-image.png` — 1200×630, Illusion wordmark + one
  tagline line on a gradient background. One-time design.
- Create `frontend/public/robots.txt`:
  ```
  User-agent: *
  Allow: /
  Sitemap: https://illusion.ai/sitemap.xml
  ```
- Create `frontend/public/sitemap.xml` manually for now (landing, pricing,
  login, register). Switch to an auto-generated one once Astro blog is in.
- Verify the site in [Google Search Console](https://search.google.com/search-console)
  and [Bing Webmaster Tools](https://www.bing.com/webmasters). Submit the
  sitemap once GSC verifies the DNS TXT record.
- Submit to Bing too — Bing powers ChatGPT's web citations, so ranking there
  matters for our own category.

### Per-route meta tags
Once the blog is in and we have real per-page content, use
[`react-helmet-async`](https://github.com/staylor/react-helmet-async) in the
React SPA routes (landing, pricing) to set per-route `<title>` + meta
description. The current `<title>` is hard-coded in `index.html` and every
route inherits it — suboptimal for pricing page ranking.

---

## Step 2 — Blog infrastructure

### Decision: Astro in the same repo, same domain, at `/blog`

Why not the existing Vite/React app:
- Vite SPA renders nothing on first paint; Google can execute JS, but it
  crawls slowly and ranks slower. For content that has to rank, SSG matters.

Why not a separate Vercel project on `blog.illusion.ai`:
- Subdomains split domain authority. Every backlink to `blog.illusion.ai`
  helps the blog; zero flows back to the marketing site. Keeping everything
  on the apex means backlinks compound.

Why Astro over Next.js:
- Zero-JS by default. Blog posts ship as pure HTML + CSS → sub-100ms LCP,
  perfect for Core Web Vitals. Next.js is fine but overkill when we don't
  need React on the blog pages.
- MDX first-class — we write posts in Markdown with JSX embedded for
  comparison tables, screenshots, callouts.
- Easy to add later if we outgrow it.

### Layout

```
illusion.ai/              ← Vite React app (current)
illusion.ai/pricing
illusion.ai/blog          ← Astro, new
illusion.ai/blog/[slug]   ← Astro, new
```

Vercel handles the routing by deploying both projects and using a root
`vercel.json` with `rewrites` to route `/blog/*` to the Astro project. Two
deploys, one domain. Standard pattern — Vercel has a docs page on it.

Alternative: move everything to Astro (which supports React islands), and
render the SPA pages as Astro pages. Cleaner long-term, more work now.
Recommendation: do the two-project rewrite first, revisit in 3 months.

### Content structure

```
blog/
  src/
    content/posts/
      2026-04-22-profound-vs-illusion.mdx
      2026-04-29-athenahq-vs-illusion.mdx
      2026-05-06-generative-engine-optimization-guide.mdx
    layouts/
      PostLayout.astro   ← H1, table of contents, author box, related posts
    components/
      CompareTable.astro
      ClaudeScreenshot.astro
      CTAButton.astro
    pages/
      blog/index.astro   ← post list
      blog/[slug].astro  ← post renderer
```

Each MDX post has frontmatter:

```yaml
---
title: "Profound vs Illusion: Which AI Search Tracker Wins in 2026?"
description: "We put Profound and Illusion head-to-head on price, features, and accuracy. Here's what we found."
slug: profound-vs-illusion
publishDate: 2026-04-22
author: "David"
tags: [comparison, profound]
hero: /blog/hero/profound-vs-illusion.png
---
```

The layout pulls these into `<title>`, `<meta description>`, OG tags, JSON-LD
`Article` structured data. One layout, correct SEO on every post.

---

## Step 3 — First 5 posts (ship in week 1)

Mix of 3 conquesting + 2 category-authority. All draftable by Claude in 20
minutes each; David edits for voice and fact-checks the comparisons.

### Conquesting posts (target competitor queries)

1. **Profound vs Illusion: Which AI Search Tracker Wins in 2026?**
   - Target: "profound vs illusion", "profound alternative"
   - Angle: Profound is enterprise-priced and slow to add new AI models;
     Illusion is built for founders and ships model updates same-week.
   - Include: price table, feature matrix, screenshot of both dashboards.

2. **AthenaHQ Review: Is It Worth It for Startups?**
   - Target: "athenahq review", "athenahq alternative", "athenahq pricing"
   - Angle: mirrors Profound's playbook — honest review calling out
     enterprise positioning. Since we're smaller than AthenaHQ, we can
     credibly claim to be the startup-friendly choice.

3. **The 7 Best AI Search Monitoring Tools in 2026**
   - Target: "AI search monitoring", "track ChatGPT mentions", "AI SEO tools"
   - List format: Profound, AthenaHQ, Otterly, Peec, PromptMonitor, Illusion,
     DIY. Mild self-bias with comparison table. Links to posts 1 and 2.
   - This is the hub. Posts 1 and 2 internally link up to it; it links down.

### Category-authority posts (target informational queries)

4. **Generative Engine Optimization: The Complete 2026 Guide**
   - Target: "generative engine optimization", "GEO SEO", "how to rank in AI"
   - Pillar post. 2,500–3,500 words. TOC, 8–10 H2s. Include:
     - What GEO is vs traditional SEO
     - How each AI model picks citations (Claude = training + Anthropic's
       indexing, ChatGPT = Bing + web tool, Gemini = Google + AI Overview)
     - 10 concrete tactics (structured data, citation-worthy stats, FAQ
       schema, etc.)
   - Should be the page Google shows for the term in 6 months.

5. **How Claude Picks Which Products to Recommend (We Ran 10,000 Queries)**
   - Target: "how does Claude recommend", "ChatGPT product recommendations"
   - Original-research post. Pull aggregate data from our own scan database.
     This is the post *only we can write* because we have the data.
   - Gets the most backlinks of any post on the list. Worth doing right.

Posts 1, 2, 3 interlink. Posts 4 and 5 interlink. Every post CTAs to
`/register` with `?utm_source=blog&utm_content=<slug>`.

---

## Step 4 — Programmatic comparison pages

After the hand-written posts are up, templated pages at scale:

```
/blog/compare/[tool-a]-vs-[tool-b]
```

For every pair in our competitor set (~6 tools → 15 pairs including ones
not involving Illusion). Fill with:
- Feature checklist pulled from each tool's pricing/features page
- Pricing comparison table
- One-paragraph recommendation

Template once, data-driven generation fills in the rest. Low-effort pages
catch very-long-tail traffic. Profound does this too.

**Caution**: Google can and does penalize thin programmatic pages. Don't
publish empty templates. Each page needs at least 500 words of real,
differentiated text. Claude can draft those fine; don't cut the human edit.

---

## Step 5 — Off-page SEO

Backlinks are the half of SEO we don't control. Don't overthink this — just
do the no-brainers:

- **Directory listings**: Product Hunt, Uneed, BetaList, SaaSHub, AlternativeTo,
  G2, Capterra, TrustPilot. Each takes ~15 minutes, each gives one backlink
  + referral traffic. Do all of them in one sitting.
- **Stratechery-adjacent newsletters**: pitch guest posts or data drops to
  AI/SEO newsletters — "The AI SEO Brief," "Mostly Metrics," "SEO Notebook."
  Offer them the "how Claude recommends products" data from post #5.
- **HN + r/SEO + r/SaaS launch posts** once the blog has 5+ posts live.
- **Reddit answer marketing**: search "AI search tool" on Reddit weekly, give
  genuinely helpful answers that link to specific blog posts (not homepage
  — Reddit bans that fast).

Don't pay for backlinks. Don't buy from PBNs. Don't use a "SaaS directory
submitter" service. All three are fast routes to a Google penalty.

---

## Step 6 — Measurement

We already have PostHog and Vercel Web Analytics. Add:

- **PostHog funnel**: `blog_post_viewed` → `blog_cta_clicked` → `register_completed`.
  Breakdowns by post slug show which content converts.
- **UTM discipline**: every blog CTA uses
  `?utm_source=blog&utm_medium=cta&utm_content=<post-slug>`. PostHog
  auto-captures utm params.
- **Google Search Console**: watch impressions and avg position per query.
  First 2 weeks: mostly brand queries. Weeks 4+: comparison queries start
  appearing. Month 3+: category queries climb.
- **A single weekly check-in**: 15 min every Monday — GSC + PostHog. Look for
  posts that got a spike of traffic but not signups (fix the CTA), or the
  opposite (double down on the topic).

Optional later: [Ahrefs Webmaster Tools](https://ahrefs.com/webmaster-tools)
is free if you verify your site. Gives backlink data that GSC doesn't.

---

## Workflow — how a post actually gets made

1. **Topic picked** from the backlog (see list above or programmatic queue).
2. **Research pass** — Claude + Tavily (same tool the marketing agent will
   use) pulls competitor features, recent news, pricing. Save to a Google Doc.
3. **Draft** — Claude writes a 1,200–2,500-word first draft with hooks and
   sections matching the Profound template.
4. **Primary research** — run Illusion's own scanner against relevant queries,
   screenshot the AI responses, paste into the draft.
5. **David edits** for voice, accuracy, and spicy opinions Claude won't write.
6. **Ship** — push the MDX file, Astro builds, Vercel deploys.
7. **Distribute** — HN post if it's good enough, LinkedIn, Twitter, submit
   to the one or two newsletters whose audience cares.

Target: **2 posts per week** for the first month (~8 posts banked before
any of them ranks). After that, 1 post per week is sustainable.

---

## Tools to add

| Tool | Why | Cost |
|---|---|---|
| Astro | Blog framework | Free |
| MDX | Post authoring | Free |
| Google Search Console | Verification, sitemap, position tracking | Free |
| Bing Webmaster Tools | Same for Bing (matters for ChatGPT citations) | Free |
| Ahrefs Webmaster Tools | Backlink data | Free with site verification |
| [Schema Markup Generator](https://technicalseo.com/tools/schema-markup-generator/) | One-off JSON-LD for home + pricing | Free |
| [OG Image Checker](https://www.opengraph.xyz/) | Debug social previews | Free |

Nothing paid. Resist the urge to subscribe to Ahrefs/Semrush until there's
real traffic to measure. GSC is 80% of the insight at 0% of the cost.

---

## Decisions made (2026-04-21)

- **OG image**: David is designing it himself — Illusion logo + tagline on
  brand gradient, 1200×630 PNG, saved to `frontend/public/og-image.png`.
  Generic image for homepage + every blog post v1. Per-post dynamic OG images
  via `@vercel/og` is a later upgrade.
- **Author byline**: "David C" on every post. Profile image to come — store
  at `blog/public/authors/david-c.jpg` and reference from the `PostLayout`
  author box + JSON-LD `author` field.
- **First post to write**: #5 — "How Claude Picks Which Products to Recommend
  (We Ran 10,000 Queries)". Highest-effort, most linkable, sets the bar.
- **Comments / discussion on posts**: off. Discussion happens on Twitter/HN.

---

## How this connects to the marketing email agent

The marketing agent (Part 3 of `PLAN_email_analytics.md`) and the blog share
the same raw-material pipeline:

- Same Tavily research step for trending AI-search news
- Same `aggregate_stats()` function for product stats we can cite
- Same Claude drafting step

When we build the marketing agent, we should consider whether the output is
one JSON schema with two render targets (email HTML + blog MDX) rather than
two separate pipelines. Defer the decision — but it's worth keeping in mind
while scoping Part 3.
