"""
Website audit crawler and report generator.

The public analyzer needs to be useful for small businesses without becoming a
security risk. This module keeps crawling deliberately small, validates every
network destination before fetching it, and falls back to deterministic findings
when the Anthropic recommendation layer is not configured.
"""
from __future__ import annotations

import ipaddress
import json
import re
import socket
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urljoin, urlparse, urlunparse
from xml.etree import ElementTree

import anthropic
import httpx

from config import settings


MAX_HTML_BYTES = 1_000_000
MAX_REDIRECTS = 4
MAX_PAGES = 6
TIMEOUT = 12.0
USER_AGENT = (
    "IllusionWebsiteAudit/1.0 (+https://www.illusion.ai; "
    "AI search visibility and website diagnostics)"
)

HIGH_VALUE_PATH_HINTS = (
    "service", "services", "about", "contact", "pricing", "faq", "locations",
    "location", "accounting", "bookkeeping", "tax", "case-studies", "reviews",
    "testimonials", "blog",
)
CTA_WORDS = (
    "book", "schedule", "call", "contact", "get a quote", "request",
    "consultation", "start", "sign up", "try", "demo", "appointment",
)
REVIEW_WORDS = ("testimonial", "review", "client", "customer", "trusted by")
FAQ_WORDS = ("faq", "frequently asked", "questions", "how much", "what is")
AI_BOTS = ("GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot",
           "Claude-SearchBot", "PerplexityBot", "Google-Extended")


class AuditError(Exception):
    """Expected audit failure with a message safe to show in the UI."""


@dataclass
class FetchResult:
    url: str
    status_code: int
    html: str
    content_type: str


def _clean_text(text: str, max_len: Optional[int] = None) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if max_len and len(text) > max_len:
        return text[:max_len].rstrip() + "..."
    return text


def _host_is_public(hostname: str) -> bool:
    host = hostname.strip("[]").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        return False

    try:
        addrs = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        except socket.gaierror:
            raise AuditError("We could not resolve that domain.")
        addrs = []
        for info in infos:
            raw = info[4][0]
            try:
                addrs.append(ipaddress.ip_address(raw))
            except ValueError:
                continue

    if not addrs:
        raise AuditError("We could not resolve that domain.")

    for ip in addrs:
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False
    return True


def normalize_url(raw_url: str) -> str:
    """Normalize and validate a public http(s) URL."""
    raw = (raw_url or "").strip()
    if not raw:
        raise AuditError("Enter a website URL to audit.")
    if "://" not in raw:
        raw = f"https://{raw}"

    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        raise AuditError("Website audits only support http and https URLs.")
    if not parsed.hostname:
        raise AuditError("Enter a valid website URL.")
    if parsed.username or parsed.password:
        raise AuditError("URLs with usernames or passwords are not supported.")
    if not _host_is_public(parsed.hostname):
        raise AuditError("That URL points to a private or local network address.")

    path = parsed.path or "/"
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        path=path,
        fragment="",
    )
    return urlunparse(normalized)


def domain_for_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed.hostname or ""


class PageParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title = ""
        self.meta: dict[str, str] = {}
        self.canonical = ""
        self.headings: dict[str, list[str]] = {"h1": [], "h2": [], "h3": []}
        self.links: list[str] = []
        self.images_total = 0
        self.images_with_alt = 0
        self.json_ld_raw: list[str] = []
        self.forms = 0
        self.buttons: list[str] = []
        self.lang = ""
        self._tag_stack: list[str] = []
        self._current_heading: Optional[str] = None
        self._current_script_jsonld = False
        self._buffer = ""
        self._text_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        tag = tag.lower()
        attrs_dict = {k.lower(): (v or "") for k, v in attrs}
        self._tag_stack.append(tag)

        if tag == "html":
            self.lang = attrs_dict.get("lang", "")
        elif tag == "meta":
            key = (attrs_dict.get("name") or attrs_dict.get("property") or "").lower()
            content = attrs_dict.get("content", "")
            if key and content:
                self.meta[key] = content
        elif tag == "link" and attrs_dict.get("rel", "").lower() == "canonical":
            self.canonical = urljoin(self.base_url, attrs_dict.get("href", ""))
        elif tag == "a" and attrs_dict.get("href"):
            self.links.append(urljoin(self.base_url, attrs_dict["href"]))
        elif tag == "img":
            self.images_total += 1
            if attrs_dict.get("alt", "").strip():
                self.images_with_alt += 1
        elif tag in self.headings:
            self._current_heading = tag
            self._buffer = ""
        elif tag == "title":
            self._buffer = ""
        elif tag == "script":
            script_type = attrs_dict.get("type", "").lower()
            self._current_script_jsonld = "ld+json" in script_type
            if self._current_script_jsonld:
                self._buffer = ""
        elif tag == "form":
            self.forms += 1
        elif tag == "button":
            self._buffer = ""

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if tag == "title":
            self.title = _clean_text(self._buffer, 180)
            self._buffer = ""
        elif tag in self.headings and self._current_heading == tag:
            value = _clean_text(self._buffer, 180)
            if value:
                self.headings[tag].append(value)
            self._current_heading = None
            self._buffer = ""
        elif tag == "script" and self._current_script_jsonld:
            if self._buffer.strip():
                self.json_ld_raw.append(self._buffer.strip())
            self._current_script_jsonld = False
            self._buffer = ""
        elif tag == "button":
            value = _clean_text(self._buffer, 80)
            if value:
                self.buttons.append(value)
            self._buffer = ""

        if self._tag_stack:
            try:
                self._tag_stack.remove(tag)
            except ValueError:
                pass

    def handle_data(self, data: str):
        if not data or any(t in {"script", "style", "noscript"} for t in self._tag_stack):
            if self._current_script_jsonld:
                self._buffer += data
            return
        if self._current_heading or (self._tag_stack and self._tag_stack[-1] in {"title", "button"}):
            self._buffer += data
        cleaned = _clean_text(data)
        if cleaned:
            self._text_chunks.append(cleaned)

    @property
    def visible_text(self) -> str:
        return _clean_text(" ".join(self._text_chunks), 8000)


def _extract_schema_types(json_ld_raw: list[str]) -> list[str]:
    types: set[str] = set()

    def visit(value):
        if isinstance(value, dict):
            raw_type = value.get("@type")
            if isinstance(raw_type, str):
                types.add(raw_type)
            elif isinstance(raw_type, list):
                types.update(str(t) for t in raw_type if t)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    for raw in json_ld_raw:
        try:
            visit(json.loads(raw))
        except Exception:
            continue
    return sorted(types)


def _same_site_url(base_url: str, candidate: str) -> bool:
    base = urlparse(base_url)
    parsed = urlparse(candidate)
    return parsed.scheme in {"http", "https"} and parsed.hostname == base.hostname


def _is_html_content(content_type: str) -> bool:
    if not content_type:
        return True
    lowered = content_type.lower()
    return "text/html" in lowered or "application/xhtml" in lowered


def _fetch_html(client: httpx.Client, url: str) -> FetchResult:
    current = normalize_url(url)
    for _ in range(MAX_REDIRECTS + 1):
        try:
            with client.stream(
                "GET",
                current,
                headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
            ) as resp:
                if 300 <= resp.status_code < 400 and resp.headers.get("location"):
                    current = normalize_url(urljoin(current, resp.headers["location"]))
                    continue
                content_type = resp.headers.get("content-type", "")
                if not _is_html_content(content_type):
                    raise AuditError("That URL did not return an HTML web page.")
                chunks = []
                total = 0
                for chunk in resp.iter_bytes():
                    total += len(chunk)
                    if total > MAX_HTML_BYTES:
                        raise AuditError("That page is too large to audit safely.")
                    chunks.append(chunk)
                html = b"".join(chunks).decode(resp.encoding or "utf-8", errors="replace")
                return FetchResult(current, resp.status_code, html, content_type)
        except httpx.TimeoutException:
            raise AuditError("The website took too long to respond.")
        except httpx.HTTPError as e:
            raise AuditError(f"We could not fetch that website ({type(e).__name__}).")
    raise AuditError("The website redirected too many times.")


def _fetch_text(client: httpx.Client, url: str, max_bytes: int = 300_000) -> str:
    try:
        resp = client.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        if resp.status_code >= 400:
            return ""
        body = resp.content[:max_bytes]
        return body.decode(resp.encoding or "utf-8", errors="replace")
    except Exception:
        return ""


def _robots_url(base_url: str) -> str:
    p = urlparse(base_url)
    return urlunparse((p.scheme, p.netloc, "/robots.txt", "", "", ""))


def _sitemap_url(base_url: str) -> str:
    p = urlparse(base_url)
    return urlunparse((p.scheme, p.netloc, "/sitemap.xml", "", "", ""))


def _parse_sitemap_urls(raw: str, base_url: str) -> list[str]:
    if not raw.strip():
        return []
    urls: list[str] = []
    try:
        root = ElementTree.fromstring(raw.encode("utf-8"))
        for loc in root.iter():
            if loc.tag.lower().endswith("loc") and loc.text:
                full = loc.text.strip()
                if _same_site_url(base_url, full):
                    urls.append(full)
    except Exception:
        urls = re.findall(r"<loc>\s*([^<]+)\s*</loc>", raw, flags=re.I)
    return urls


def _ai_bots_blocked_by_robots(raw: str) -> list[str]:
    if not raw:
        return []
    blocked: set[str] = set()
    current_agents: list[str] = []
    for raw_line in raw.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = [part.strip() for part in line.split(":", 1)]
        key = key.lower()
        if key == "user-agent":
            current_agents = [value]
        elif key == "disallow" and value.strip() == "/":
            for agent in current_agents:
                for bot in AI_BOTS:
                    if agent == "*" or agent.lower() == bot.lower():
                        blocked.add(bot)
    return sorted(blocked)


def _score_from_findings(findings: list[dict], categories: set[str]) -> int:
    score = 100
    weights = {"high": 16, "medium": 9, "low": 4}
    for finding in findings:
        if finding.get("category") in categories:
            score -= weights.get(finding.get("severity"), 6)
    return max(0, min(100, score))


def _add_finding(findings: list[dict], category: str, severity: str, title: str,
                 evidence: str, fix: str, expected_impact: str, effort: str,
                 suggested_copy: Optional[str] = None):
    item = {
        "category": category,
        "severity": severity,
        "title": title,
        "evidence": evidence,
        "fix": fix,
        "expected_impact": expected_impact,
        "effort": effort,
    }
    if suggested_copy:
        item["suggested_copy"] = suggested_copy
    findings.append(item)


def _choose_extra_pages(base_url: str, parser: PageParser, sitemap_urls: list[str]) -> list[str]:
    candidates: list[tuple[int, str]] = []
    seen: set[str] = set()

    for source_idx, link in enumerate(parser.links + sitemap_urls):
        if not _same_site_url(base_url, link):
            continue
        parsed = urlparse(link)._replace(fragment="", query="")
        clean = urlunparse(parsed)
        if clean in seen or clean.rstrip("/") == base_url.rstrip("/"):
            continue
        seen.add(clean)
        path = parsed.path.lower()
        score = 0
        for idx, hint in enumerate(HIGH_VALUE_PATH_HINTS):
            if hint in path:
                score += 40 - idx
        if path.count("/") <= 2:
            score += 5
        score -= source_idx // 20
        candidates.append((score, clean))

    candidates.sort(key=lambda item: item[0], reverse=True)
    return [url for score, url in candidates[:MAX_PAGES - 1] if score >= 0]


def _page_payload(result: FetchResult, parser: PageParser) -> dict:
    meta_desc = parser.meta.get("description", "")
    word_count = len(re.findall(r"\w+", parser.visible_text))
    return {
        "url": result.url,
        "status_code": result.status_code,
        "title": parser.title,
        "meta_description": _clean_text(meta_desc, 220),
        "h1": parser.headings["h1"][:3],
        "h2": parser.headings["h2"][:8],
        "word_count": word_count,
        "canonical": parser.canonical,
        "meta_robots": parser.meta.get("robots", ""),
        "schema_types": _extract_schema_types(parser.json_ld_raw),
        "links_found": len(parser.links),
        "images_total": parser.images_total,
        "images_with_alt": parser.images_with_alt,
    }


def _build_deterministic_report(normalized_url: str, pages: list[dict], parsers: list[PageParser],
                                robots_txt: str, sitemap_urls: list[str]) -> dict:
    homepage = pages[0]
    all_text = " ".join(p.visible_text for p in parsers).lower()
    all_paths = " ".join(urlparse(p["url"]).path.lower() for p in pages)
    schema_types = sorted({t for page in pages for t in (page.get("schema_types") or [])})
    total_images = sum(p.get("images_total") or 0 for p in pages)
    images_with_alt = sum(p.get("images_with_alt") or 0 for p in pages)
    alt_rate = (images_with_alt / total_images) if total_images else 1
    blocked_bots = _ai_bots_blocked_by_robots(robots_txt)

    email_found = bool(re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", all_text))
    phone_found = bool(re.search(r"(\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}", all_text))
    cta_found = any(word in all_text for word in CTA_WORDS) or any(
        any(word in button.lower() for word in CTA_WORDS)
        for parser in parsers
        for button in parser.buttons
    )
    review_found = any(word in all_text for word in REVIEW_WORDS)
    faq_found = any(word in all_text for word in FAQ_WORDS) or "faq" in all_paths
    service_page_found = any("service" in urlparse(p["url"]).path.lower() for p in pages)
    location_signal_found = any(
        word in all_text for word in ("near me", "serving", "florida", "local", "county")
    ) or "location" in all_paths
    local_schema_found = any(t in schema_types for t in ("LocalBusiness", "ProfessionalService", "AccountingService"))

    findings: list[dict] = []

    if not homepage.get("title"):
        _add_finding(
            findings, "seo", "high", "Add a clear homepage title tag",
            "The homepage does not expose a title tag.",
            "Write a concise title that includes the business name, primary service, and location or audience.",
            "Helps Google, AI crawlers, and customers understand what the business does before opening the page.",
            "low",
        )
    elif len(homepage["title"]) < 25:
        _add_finding(
            findings, "seo", "medium", "Make the title tag more descriptive",
            f"Current title: \"{homepage['title']}\"",
            "Expand the title with the main service and location or target customer.",
            "Improves search snippets and gives AI systems a clearer label for the business.",
            "low",
        )

    if not homepage.get("meta_description"):
        _add_finding(
            findings, "seo", "medium", "Add a meta description",
            "The homepage has no meta description.",
            "Add a one-sentence description of who you help, what you do, and how to contact you.",
            "Improves click appeal in search and gives AI summarizers a clean business description.",
            "low",
        )

    h1s = homepage.get("h1") or []
    if not h1s:
        _add_finding(
            findings, "content", "high", "Add one plain-language H1",
            "The homepage does not have a visible H1 heading.",
            "Use one headline that says exactly what the business is and who it serves.",
            "Makes the page easier for visitors and answer engines to classify.",
            "low",
            "Tax and bookkeeping services for small businesses in Florida",
        )
    elif len(h1s[0].split()) < 4:
        _add_finding(
            findings, "content", "medium", "Make the main headline more specific",
            f"Current H1: \"{h1s[0]}\"",
            "Add the service, audience, and location instead of using a short brand-only headline.",
            "Improves human comprehension and AI answer quality.",
            "low",
        )

    if not cta_found:
        _add_finding(
            findings, "user_experience", "high", "Add a strong contact call to action",
            "The crawler did not find obvious phrases like book, call, schedule, contact, or get a quote.",
            "Place a visible CTA near the top of the homepage and repeat it on service pages.",
            "More visitors will know the next step, and AI summaries can mention how to engage the business.",
            "low",
        )

    if not (email_found or phone_found):
        _add_finding(
            findings, "local_seo", "high", "Show contact information in crawlable text",
            "No email address or US-style phone number was found in the crawled text.",
            "Add phone/email details in the header, footer, or contact section as real text, not only inside an image.",
            "Builds trust for local customers and gives search engines verifiable business signals.",
            "low",
        )

    if not local_schema_found:
        _add_finding(
            findings, "structured_data", "high", "Add LocalBusiness or ProfessionalService schema",
            f"Detected schema types: {', '.join(schema_types) if schema_types else 'none'}",
            "Add JSON-LD with business name, URL, phone, address/service area, opening hours, and sameAs profiles.",
            "Structured data helps Google and AI systems confidently identify the business entity.",
            "medium",
        )

    if not service_page_found and len(pages) < 3:
        _add_finding(
            findings, "content", "medium", "Create dedicated service pages",
            "The crawl did not find obvious service pages.",
            "Create one page per main service with who it is for, what is included, pricing cues, FAQs, and a CTA.",
            "Specific service pages give AI systems quotable evidence and give customers a clearer path.",
            "medium",
        )

    if not location_signal_found:
        _add_finding(
            findings, "local_seo", "medium", "Add local service-area signals",
            "The crawled pages did not show strong location or service-area language.",
            "Mention the city, region, or service area in headings, footer copy, and service descriptions.",
            "Local customers and local-intent searches need geographic confidence.",
            "low",
        )

    if not review_found:
        _add_finding(
            findings, "user_experience", "medium", "Add reviews or testimonials",
            "No review/testimonial language was detected.",
            "Add 2-4 real customer testimonials, review snippets, or links to Google Business reviews.",
            "Trust proof matters for humans and gives AI systems third-party-style evidence to summarize.",
            "low",
        )

    if not faq_found:
        _add_finding(
            findings, "ai_search", "medium", "Add a short FAQ section",
            "No FAQ-style content was detected.",
            "Add answers to common buyer questions: pricing, turnaround time, who you serve, and when to contact you.",
            "Question-answer content maps directly to how people ask ChatGPT, Claude, and Google AI Overviews.",
            "low",
        )

    if total_images and alt_rate < 0.7:
        _add_finding(
            findings, "seo", "low", "Improve image alt text coverage",
            f"{images_with_alt}/{total_images} crawled images had alt text.",
            "Add descriptive alt text to important images, especially logos, team photos, service graphics, and trust badges.",
            "Improves accessibility and gives crawlers more context.",
            "low",
        )

    if blocked_bots:
        _add_finding(
            findings, "ai_search", "high", "Review AI crawler blocks in robots.txt",
            f"robots.txt appears to block: {', '.join(blocked_bots)}",
            "Decide which AI crawlers should read public marketing pages. If visibility is the goal, avoid blanket disallow rules for answer-engine crawlers.",
            "If AI crawlers cannot access the site, the business is less likely to be cited or summarized accurately.",
            "low",
        )

    if not sitemap_urls:
        _add_finding(
            findings, "technical", "low", "Publish or expose a sitemap",
            "No sitemap URLs were found from /sitemap.xml or robots.txt.",
            "Generate a sitemap.xml and reference it from robots.txt.",
            "Helps search engines and AI retrieval systems discover important pages.",
            "low",
        )

    ux_score = _score_from_findings(findings, {"user_experience", "local_seo"})
    seo_score = _score_from_findings(findings, {"seo", "local_seo", "technical", "structured_data"})
    ai_score = _score_from_findings(findings, {"ai_search", "structured_data", "content"})
    overall_score = round((ux_score + seo_score + ai_score) / 3)

    strengths: list[str] = []
    if homepage.get("title"):
        strengths.append("Homepage has a crawlable title tag.")
    if homepage.get("h1"):
        strengths.append("Homepage includes a visible main heading.")
    if cta_found:
        strengths.append("Calls to action are visible in the crawled copy.")
    if schema_types:
        strengths.append(f"Structured data detected: {', '.join(schema_types[:4])}.")
    if not strengths:
        strengths.append("The website is reachable and can be crawled for baseline analysis.")

    signals = {
        "domain": domain_for_url(normalized_url),
        "schema_types": schema_types,
        "has_email": email_found,
        "has_phone": phone_found,
        "has_cta": cta_found,
        "has_reviews": review_found,
        "has_faq": faq_found,
        "has_service_page": service_page_found,
        "has_location_signal": location_signal_found,
        "local_schema_found": local_schema_found,
        "blocked_ai_bots": blocked_bots,
        "sitemap_url_count": len(sitemap_urls),
        "image_alt_rate": round(alt_rate, 2),
        "strengths": strengths[:5],
    }

    summary = (
        "The site is crawlable, but the highest-leverage fixes are about clarity, "
        "trust, and structured business signals. Prioritize the high-severity items "
        "first so visitors and AI answer engines can quickly understand who the "
        "business serves and how to contact it."
    )
    if overall_score >= 80:
        summary = (
            "The site has a solid foundation for customers and AI search. The next gains "
            "come from adding more specific service, location, FAQ, and trust proof signals."
        )

    return {
        "executive_summary": summary,
        "scores": {
            "overall": overall_score,
            "ux": ux_score,
            "seo": seo_score,
            "ai": ai_score,
        },
        "findings": findings[:12],
        "signals": signals,
    }


AI_SYSTEM_PROMPT = """\
You are a practical website optimization strategist for startups and local service businesses.
You specialize in user experience, SEO, local SEO, and AI answer-engine visibility.

Return ONLY valid JSON with this exact shape:
{
  "executive_summary": "2-3 plain-English sentences",
  "scores": {"overall": 0-100, "ux": 0-100, "seo": 0-100, "ai": 0-100},
  "findings": [
    {
      "category": "user_experience|seo|local_seo|structured_data|content|ai_search|technical",
      "severity": "high|medium|low",
      "title": "short finding title",
      "evidence": "specific evidence from the crawl",
      "fix": "specific action the site owner can take",
      "expected_impact": "why this matters",
      "effort": "low|medium|high",
      "suggested_copy": "optional copy the user can paste"
    }
  ]
}

Keep advice concrete and honest. Favor fixes that a small business can ship without hiring an
enterprise SEO agency. Do not invent facts that were not present in the crawl data.\
"""


def _try_ai_polish(deterministic: dict, pages: list[dict], normalized_url: str) -> dict:
    if not settings.anthropic_api_key:
        deterministic["model_used"] = "deterministic"
        return deterministic

    payload = {
        "url": normalized_url,
        "deterministic_report": deterministic,
        "pages": pages,
    }
    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        message = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=2200,
            system=AI_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": (
                    "Use this crawl and deterministic report to produce the final website audit JSON. "
                    "You may refine wording and prioritization, but preserve evidence-based scoring.\n\n"
                    + json.dumps(payload, ensure_ascii=False)[:16000]
                ),
            }],
        )
        raw = "".join(block.text for block in message.content if getattr(block, "type", None) == "text")
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.S).strip()
        parsed = json.loads(raw)
        parsed["model_used"] = settings.anthropic_model
        return _normalize_report(parsed, deterministic)
    except Exception as e:
        print(f"[website_audits] AI polish failed: {type(e).__name__}: {e}")
        deterministic["model_used"] = "deterministic"
        return deterministic


def _normalize_report(report: dict, fallback: dict) -> dict:
    scores = report.get("scores") or fallback.get("scores") or {}
    normalized_scores = {}
    for key in ("overall", "ux", "seo", "ai"):
        try:
            normalized_scores[key] = max(0, min(100, int(scores.get(key, fallback["scores"][key]))))
        except Exception:
            normalized_scores[key] = fallback["scores"][key]

    findings = []
    for finding in report.get("findings") or []:
        if not isinstance(finding, dict):
            continue
        severity = (finding.get("severity") or "medium").lower()
        if severity not in {"high", "medium", "low"}:
            severity = "medium"
        category = (finding.get("category") or "seo").lower()
        if category not in {"user_experience", "seo", "local_seo", "structured_data", "content", "ai_search", "technical"}:
            category = "seo"
        item = {
            "category": category,
            "severity": severity,
            "title": _clean_text(finding.get("title") or "Improve website clarity", 120),
            "evidence": _clean_text(finding.get("evidence") or "", 260),
            "fix": _clean_text(finding.get("fix") or "", 420),
            "expected_impact": _clean_text(finding.get("expected_impact") or "", 300),
            "effort": (finding.get("effort") or "medium").lower(),
        }
        if finding.get("suggested_copy"):
            item["suggested_copy"] = _clean_text(finding.get("suggested_copy"), 360)
        if item["title"] and item["fix"]:
            findings.append(item)

    if not findings:
        findings = fallback.get("findings") or []

    return {
        "executive_summary": _clean_text(
            report.get("executive_summary") or fallback.get("executive_summary") or "",
            700,
        ),
        "scores": normalized_scores,
        "findings": findings[:12],
        "signals": fallback.get("signals") or {},
        "model_used": report.get("model_used") or fallback.get("model_used") or settings.anthropic_model,
    }


def run_website_audit(raw_url: str) -> dict:
    """Fetch a small site sample and return a structured audit report."""
    normalized_url = normalize_url(raw_url)
    pages: list[dict] = []
    parsers: list[PageParser] = []

    with httpx.Client(timeout=TIMEOUT, follow_redirects=False) as client:
        home = _fetch_html(client, normalized_url)
        parser = PageParser(home.url)
        parser.feed(home.html)
        pages.append(_page_payload(home, parser))
        parsers.append(parser)

        robots_txt = _fetch_text(client, _robots_url(home.url))
        sitemap_urls = _parse_sitemap_urls(_fetch_text(client, _sitemap_url(home.url)), home.url)
        for match in re.findall(r"(?im)^sitemap:\s*(\S+)", robots_txt):
            sitemap_urls.extend(_parse_sitemap_urls(_fetch_text(client, match.strip()), home.url))

        for url in _choose_extra_pages(home.url, parser, sitemap_urls):
            try:
                result = _fetch_html(client, url)
                page_parser = PageParser(result.url)
                page_parser.feed(result.html)
                pages.append(_page_payload(result, page_parser))
                parsers.append(page_parser)
            except AuditError:
                continue

    deterministic = _build_deterministic_report(home.url, pages, parsers, robots_txt, sitemap_urls)
    final_report = _try_ai_polish(deterministic, pages, home.url)
    return {
        "normalized_url": home.url,
        "domain": domain_for_url(home.url),
        "executive_summary": final_report["executive_summary"],
        "scores": final_report["scores"],
        "findings": final_report["findings"],
        "crawled_pages": pages,
        "extracted_signals": final_report.get("signals") or {},
        "model_used": final_report.get("model_used") or "deterministic",
    }
