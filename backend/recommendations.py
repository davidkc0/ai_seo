"""
Claude-powered SEO / AI-Overview recommendations.

After a scan completes we pass Claude:
  1. Product metadata (name, category, competitors, keywords)
  2. Aggregated LLM mention stats across Claude/GPT/Gemini/Perplexity
  3. A handful of representative LLM response excerpts
  4. Google AI Overview text + cited sources for the primary query

Claude returns a structured JSON diagnosis + prioritized action list that the
frontend renders on the dashboard. We call Anthropic directly (not OpenRouter)
because we want reliable JSON-mode output and because David's Anthropic key is
already live on Railway — saves the user configuring another vendor.
"""
import json
import re
from typing import Optional

import anthropic

from config import settings


# Keep the prompt compact — Claude Sonnet's tool-free JSON mode is reliable
# as long as we're very explicit about schema.
SYSTEM_PROMPT = """\
You are a senior SEO strategist specializing in AI search (Google AI Overview, ChatGPT, \
Claude, Perplexity, Gemini). You give crisp, evidence-based advice tailored to how each \
AI system actually cites and surfaces sources.

You will be given structured data about a SaaS product and how it currently fares across \
LLM answers and Google's AI Overview. Return ONLY a JSON object — no prose before or after \
— matching this schema exactly:

{
  "executive_summary": "2-3 sentence diagnosis of where the product stands in AI search today",
  "strengths": ["short factual strength", "..."],
  "weaknesses": ["short factual weakness", "..."],
  "actions": [
    {
      "priority": "high" | "medium" | "low",
      "title": "Short imperative action (e.g. 'Publish a category-comparison article')",
      "rationale": "1-3 sentence explanation grounded in the data provided, ideally \
referencing specific competitors or cited sources."
    }
  ]
}

Guidance:
- Provide 3-6 actions, ordered by priority (high first).
- Prefer concrete, shippable actions (publish X post, add Y schema, pitch Z publication) \
over vague advice ("improve content quality").
- When Google AI Overview cites competitors or third-party publications, suggest getting \
featured in those same publications rather than just outranking them.
- Reference the ACTUAL numbers / competitor names from the data.
- If data is thin (few scans, no AI Overview returned), say so in the summary and keep \
actions conservative.
- Output valid JSON with double quotes. Do not wrap in markdown fences.\
"""


def _format_scan_stats(scan_results: list[dict], product_name: str) -> str:
    """Compact stats block for the prompt."""
    if not scan_results:
        return "No scan results available."

    by_provider: dict[str, dict] = {}
    for r in scan_results:
        p = r.get("ai_model", "unknown")
        entry = by_provider.setdefault(p, {"total": 0, "mentions": 0, "positions": []})
        entry["total"] += 1
        if r.get("product_mentioned"):
            entry["mentions"] += 1
            if r.get("mention_position"):
                entry["positions"].append(r["mention_position"])

    lines = []
    for provider, s in by_provider.items():
        rate = (s["mentions"] / s["total"] * 100) if s["total"] else 0
        best = min(s["positions"]) if s["positions"] else None
        best_str = f", best rank #{best}" if best else ""
        lines.append(f"- {provider}: {s['mentions']}/{s['total']} mentions ({rate:.0f}%{best_str})")

    # Competitors seen
    all_comp: list[str] = []
    for r in scan_results:
        all_comp.extend(r.get("competitors_mentioned") or [])
    comp_counts: dict[str, int] = {}
    for c in all_comp:
        comp_counts[c] = comp_counts.get(c, 0) + 1
    top_comp = sorted(comp_counts.items(), key=lambda kv: -kv[1])[:8]
    if top_comp:
        comp_line = ", ".join(f"{name} ({n})" for name, n in top_comp)
        lines.append(f"- Competitors mentioned in same responses: {comp_line}")

    return "\n".join(lines)


def _format_response_samples(scan_results: list[dict], product_name: str, max_samples: int = 4) -> str:
    """Pick a mix of 'mentioned' and 'not mentioned' samples for Claude to chew on."""
    if not scan_results:
        return "(no samples)"

    mentioned = [r for r in scan_results if r.get("product_mentioned")][:2]
    missed = [r for r in scan_results if not r.get("product_mentioned")][:2]
    picks = mentioned + missed

    out: list[str] = []
    for r in picks[:max_samples]:
        tag = "MENTIONED" if r.get("product_mentioned") else "NOT MENTIONED"
        provider = r.get("ai_model", "?")
        query = (r.get("query") or "").strip()[:160]
        body = (r.get("full_response") or "").strip()
        # Clip long responses — Claude doesn't need the full 1k tokens.
        if len(body) > 900:
            body = body[:900] + "..."
        out.append(f"[{tag} · {provider}] Q: {query}\nA: {body}")
    return "\n\n".join(out)


def _format_ai_overview(ai_overview: Optional[dict]) -> str:
    """Format the Google AI Overview block for the prompt."""
    if not ai_overview or not ai_overview.get("was_returned"):
        return ("Google did not return an AI Overview for the primary category query. "
                "This alone is a signal — the category may not trigger AI Overview, "
                "or Google lacks authoritative sources to summarize.")

    lines = ["--- Google AI Overview text ---",
             (ai_overview.get("overview_text") or "(no text)").strip()[:2500]]
    refs = ai_overview.get("references") or []
    if refs:
        lines.append("")
        lines.append("--- Cited sources (in order) ---")
        for i, ref in enumerate(refs[:10], 1):
            src = ref.get("source") or ""
            title = ref.get("title") or ""
            url = ref.get("url") or ""
            lines.append(f"{i}. {title} — {src} ({url})")
    return "\n".join(lines)


def build_prompt(product: dict, scan_results: list[dict], ai_overview: Optional[dict]) -> str:
    """Assemble the user-turn prompt Claude will analyze."""
    competitors = product.get("competitors") or []
    keywords = product.get("keywords") or []
    pieces = [
        "## Product",
        f"Name: {product['name']}",
        f"Category: {product['category']}",
        f"Use case: {product.get('use_case') or '(not specified)'}",
        f"Competitors: {', '.join(competitors) if competitors else '(none listed)'}",
        f"Keywords: {', '.join(keywords) if keywords else '(none listed)'}",
        "",
        "## Mention stats across 4 LLMs (this scan)",
        _format_scan_stats(scan_results, product["name"]),
        "",
        "## Sample responses (verbatim, clipped)",
        _format_response_samples(scan_results, product["name"]),
        "",
        "## Google AI Overview (primary query)",
        _format_ai_overview(ai_overview),
        "",
        "Produce the JSON per the schema in your system instructions.",
    ]
    return "\n".join(pieces)


def _strip_code_fences(text: str) -> str:
    """Claude occasionally wraps JSON in ```json fences despite instructions."""
    text = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*)```\s*$", text, re.DOTALL)
    if fence:
        return fence.group(1).strip()
    return text


def _empty_result(summary: str, model_used: str) -> dict:
    return {
        "executive_summary": summary,
        "strengths": [],
        "weaknesses": [],
        "actions": [],
        "model_used": model_used,
    }


def generate_recommendations(
    product: dict,
    scan_results: list[dict],
    ai_overview: Optional[dict],
) -> dict:
    """
    Returns a dict with the Recommendation model fields. Never raises —
    if Claude is unreachable or returns malformed JSON, returns an empty
    result with an apologetic executive_summary.
    """
    model = settings.anthropic_model

    if not settings.anthropic_api_key:
        return _empty_result(
            "Recommendations engine not configured — set ANTHROPIC_API_KEY on the server.",
            model,
        )

    if not scan_results:
        return _empty_result(
            "No scan data yet — run a scan first.",
            model,
        )

    user_prompt = build_prompt(product, scan_results, ai_overview)

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        message = client.messages.create(
            model=model,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = "".join(
            block.text for block in message.content if getattr(block, "type", None) == "text"
        )
        raw = _strip_code_fences(raw)
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[recommendations] JSON parse failed: {e} · raw: {raw[:300]}")
        return _empty_result(
            "Recommendations engine returned malformed output — retry the scan.",
            model,
        )
    except Exception as e:
        print(f"[recommendations] Claude call failed: {type(e).__name__}: {e}")
        return _empty_result(
            f"Recommendations engine hit an error ({type(e).__name__}). Scan data is still available.",
            model,
        )

    # Defensive: normalize shape in case Claude drops a field
    actions = parsed.get("actions") or []
    normalized_actions = []
    for a in actions:
        if not isinstance(a, dict):
            continue
        priority = (a.get("priority") or "medium").lower()
        if priority not in ("high", "medium", "low"):
            priority = "medium"
        normalized_actions.append({
            "priority": priority,
            "title": (a.get("title") or "").strip(),
            "rationale": (a.get("rationale") or "").strip(),
        })

    return {
        "executive_summary": (parsed.get("executive_summary") or "").strip()
            or "Analysis complete — see actions below.",
        "strengths": [s for s in (parsed.get("strengths") or []) if isinstance(s, str)][:6],
        "weaknesses": [s for s in (parsed.get("weaknesses") or []) if isinstance(s, str)][:6],
        "actions": normalized_actions[:8],
        "model_used": model,
    }
