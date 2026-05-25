# Original Data Asset Playbook

## Goal

Publish a credible research post titled **“What 25 Small Business Websites Get Wrong About AI Search.”**

The post should prove Illusion’s practical point: most small-business AI search problems start with website clarity, trust, crawlability, local signals, and structured data, not expensive enterprise AI SEO retainers.

## Collection Workflow

1. Audit 25 public English-language small-business or startup websites.
2. Prefer the terminal batch runner over clicking through the analyzer UI:
   `python3 growth/run_audit_batch.py --limit 1` for a test run, then run the rest once the output looks sane.
3. Record each completed report in `growth/ai-search-audit-research-template.csv`.
4. Keep URLs and contact emails private in the sheet. Do not publish names, emails, URLs, or uniquely identifying copy.
5. If a site fails to crawl, replace it. Optionally note the failed crawl separately, but do not count it in the 25-site sample.

Sample mix:

- `SB-001` to `SB-005`: accounting, bookkeeping, or tax firms
- `SB-006` to `SB-010`: home service businesses
- `SB-011` to `SB-015`: professional service businesses
- `SB-016` to `SB-020`: local health, wellness, or service businesses
- `SB-021` to `SB-025`: startup, SaaS, agency, or consultant sites

## Coding Rules

Use `TRUE` / `FALSE` for issue columns.

Only mark an issue as `TRUE` when the audit report explicitly supports it:

- `missing_clear_h1`: report says H1 is missing or main headline is too vague.
- `missing_meta_description`: report says the homepage has no meta description.
- `weak_or_missing_cta`: report says no obvious book/call/contact/demo/get-quote CTA was found.
- `missing_contact_info`: report says no crawlable phone or email was found.
- `missing_local_schema`: report says LocalBusiness, ProfessionalService, or equivalent schema is missing.
- `missing_service_pages`: report says obvious service pages were not found.
- `weak_location_signals`: report says local/service-area language is weak or absent.
- `missing_reviews_or_testimonials`: report says review/testimonial language was not detected.
- `missing_faq`: report says FAQ-style content was not detected.
- `poor_image_alt_coverage`: report says image alt text coverage is weak.
- `ai_crawler_block_detected`: report says robots.txt blocks one or more AI crawlers.
- `missing_sitemap`: report says no sitemap was found from `/sitemap.xml` or `robots.txt`.

If a report does not mention a signal, leave the related issue as `FALSE` or blank. Do not infer beyond the audit output.

## Rubric Rules

Use `growth/research-rubric-and-stat-verification.md` before publishing any data claims.

Score the ten rubric columns from `0` to `2`:

- service clarity
- location or audience clarity
- trust signals
- crawlability
- structured data
- FAQ / answerability
- CTA clarity
- content depth
- AI crawler awareness
- mobile/performance

Important: the analyzer does not run Lighthouse or Core Web Vitals. Only publish a mobile/performance stat if it is manually verified with a clear method.

For SaaS/startup/remote rows, treat the location category as audience clarity. A remote SaaS site should not be penalized for missing city/service-area content if it clearly explains its buyer and use case.

## Analysis Checklist

After the 25 rows are filled:

- Calculate average and median for `overall_score`, `ux_score`, `seo_score`, and `ai_score`.
- Count each issue column and convert to a percentage out of 25.
- Identify the 6-8 most common recurring issues.
- Identify the top 5 high-severity issues from `top_finding_1`, `top_finding_2`, and `top_finding_3`.
- Identify the top 5 low-effort fixes by reviewing finding text and recommendation notes.
- Create score distribution buckets:
  - `0-49`
  - `50-69`
  - `70-84`
  - `85+`
- Fill `growth/publishable-stat-verification.csv` for every stat that will appear in the article.
- Do not publish percentages from automated flags alone. Every counted row behind a binary stat needs a spot-check.

Suggested spreadsheet formulas:

- Average overall: `=AVERAGE(G2:G26)`
- Median overall: `=MEDIAN(G2:G26)`
- Count missing schema: `=COUNTIF(V2:V26,TRUE)`
- Percent missing schema: `=COUNTIF(V2:V26,TRUE)/25`
- Count 0-49 overall: `=COUNTIFS(G2:G26,">=0",G2:G26,"<=49")`
- Count 50-69 overall: `=COUNTIFS(G2:G26,">=50",G2:G26,"<=69")`
- Count 70-84 overall: `=COUNTIFS(G2:G26,">=70",G2:G26,"<=84")`
- Count 85+ overall: `=COUNTIF(G2:G26,">=85")`

## Publication Checklist

Use `blog/src/content/posts/what-25-small-business-websites-get-wrong-about-ai-search.mdx`.

Before publishing:

- Replace every bracketed placeholder.
- Change `draft: true` to `draft: false`.
- Verify no URLs, business names, or uniquely identifying copy appear in the post.
- Verify every published number in `growth/publishable-stat-verification.csv`.
- Do not publish a claim like “37/50 lacked useful FAQ content” or “X/25 lacked useful FAQ content” unless the counted rows were spot-checked.
- Use careful language: “in this sample,” “Illusion detected,” and “may make AI search visibility harder.”
- Do not claim the audit proves rankings or AI-answer inclusion.
- Add the final post URL to `frontend/public/sitemap.xml`.
- Add the final URL to `frontend/public/llms.txt` under Core Guides.
- Run `npm run build` in `blog` and `frontend`.
- Submit the final URL in Google Search Console.

## Distribution Copy

### LinkedIn Founder Post

I audited 25 small-business and startup websites with Illusion’s AI Website Analyzer.

The pattern was pretty clear: most AI search problems are not mysterious.

They are things like unclear homepage copy, missing service pages, weak local signals, no schema, no FAQ content, thin trust proof, and contact info that is harder for crawlers to verify.

Before you pay $300-$2,000/month for an AI SEO platform, make sure your own website explains what you do clearly enough for customers, Google, and answer engines to understand it.

I wrote up the anonymized findings here: [POST_URL]

You can run the same audit for free: https://www.illusion.ai/analyze

### X Thread

I audited 25 small-business websites for AI search readiness.

The biggest issues were not exotic.

They were mostly:

1. unclear positioning
2. weak local signals
3. missing schema
4. no FAQ content
5. thin trust proof
6. hidden or weak contact CTAs

AI search optimization is not magic. A lot of it is making your website easier to understand.

Full breakdown: [POST_URL]

Free audit: https://www.illusion.ai/analyze

### Teardown Post Template

Anonymous website audit note:

One [industry] site looked polished, but Illusion detected [finding].

Why that matters: [impact].

The fix is not a six-month SEO project. It is [specific low-effort fix].

This is why I think small businesses should run a website audit before buying an expensive AI SEO platform.

Free audit: https://www.illusion.ai/analyze
