# Research Rubric and Stat Verification

This governs the original-data post:

**What 25 Small Business Websites Get Wrong About AI Search**

The sample is currently **25 sites**, not 50. Do not describe it as a 50-site study unless the sample is expanded and the sheet is rerun.

## Fairness Check

Illusion's analyzer is a fair source for website clarity and AI-search readiness patterns when the claims stay inside what the crawler actually checks:

- service clarity
- location or audience clarity
- trust signals
- crawlability
- structured data
- FAQ / answerability
- CTA clarity
- content depth
- AI crawler awareness

The current analyzer is **not** a full mobile or performance audit. It does not run Lighthouse, collect Core Web Vitals, or visually inspect responsive layout. For this research, mobile/performance can only be scored as a lightweight manual/proxy category unless we add a real performance test.

Do not publish a mobile/performance finding unless it is manually verified from the page, Lighthouse/PageSpeed, or a clearly documented proxy such as missing viewport metadata.

## Rubric

Use a 0-2 score for each category.

- `0`: missing, blocked, or materially weak
- `1`: partially present but thin, vague, hidden, or inconsistent
- `2`: clear, crawlable, and useful

For local service businesses, score location clarity by city, service area, address, local pages, and local copy.

For SaaS/startup/remote businesses, score the same category as **audience clarity**: who the product is for, what market it serves, and what use case it owns. Do not punish a remote SaaS site for not having a city page.

### Categories

| Category | 0 | 1 | 2 |
| --- | --- | --- | --- |
| Service clarity | Hard to tell what the business does | Service is present but vague or buried | Clear service/product, audience, and promise above the fold |
| Location/audience clarity | No useful location or audience signal | Some signal, but weak or inconsistent | Clear city/service area or clear startup audience/use case |
| Trust signals | No reviews, credentials, team, case proof, or affiliations | One trust signal exists but is weak or hard to verify | Multiple visible trust signals in crawlable text |
| Crawlability | Important content blocked, missing, or mostly inaccessible | Crawlable homepage but weak discovery | Homepage plus key pages/sitemap/robots are discoverable |
| Structured data | No useful schema | Generic or incomplete schema | LocalBusiness, ProfessionalService, Organization, Product, FAQ, or relevant schema is present and useful |
| FAQ/answerability | No answer-style content | Some questions answered informally | Clear FAQ or buyer-question sections with direct answers |
| CTA clarity | No obvious next step | CTA exists but weak, inconsistent, or buried | Clear contact/book/demo/get-quote CTA near key decision points |
| Content depth | Thin one-page or generic content | Some depth but gaps in services, audience, proof, or process | Service/product pages explain what is included, who it is for, and how to act |
| AI crawler awareness | AI crawler blocks or no obvious robots awareness | robots.txt exists but ambiguous | Public marketing pages are available and no relevant AI crawler blocks are detected |
| Mobile/performance | Manually verified major mobile/performance issue | Usable but some mobile/performance concern | Manually verified usable mobile experience or no clear lightweight issue detected |

Optional research score:

`rubric_total_score = SUM(category scores) / 20 * 100`

This score is for internal analysis only unless every category has been reviewed consistently. The article can still publish analyzer scores separately as “Illusion audit scores.”

## Verification Rules

Every publishable stat needs a row in:

`growth/publishable-stat-verification.csv`

Do not publish a stat unless:

- the source column(s) are listed
- the numerator and denominator are recorded
- every counted row has been spot-checked against the raw audit result or the public page
- the verification status is `verified`
- the stat is phrased with “in this sample” or equivalent limited language

For binary findings, spot-check every row counted as `TRUE`.

Example: do not publish “12/25 lacked useful FAQ content” until all 12 `missing_faq=TRUE` rows have been checked against the audit findings and, when needed, the public page.

For averages and medians, verify:

- no rows included in the calculation have blank scores
- the formula range is correct
- the sample denominator is correct
- failed crawls were replaced or clearly excluded

For anonymous examples, verify:

- the example is paraphrased
- no business name, URL, owner name, direct review quote, address, or uniquely identifying copy is included
- the example matches the raw finding

## Publishable Language

Use:

- “In this 25-site sample...”
- “Illusion detected...”
- “This may make AI search visibility harder...”
- “The audit suggests...”

Avoid:

- “Small businesses all...”
- “These sites cannot rank...”
- “This proves AI systems will not recommend them...”
- “Mobile performance was bad...” unless verified with a real mobile/performance check
