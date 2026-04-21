"""
SerpAPI → Google AI Overview integration.

Flow:
  1. Call /search.json with engine=google&q=<query>
  2. If the response already contains an `ai_overview` block, we're done.
  3. If it contains `ai_overview.page_token`, do a follow-up call to
     /search.json with engine=google_ai_overview&page_token=<token>
     (Google sometimes defers the AI Overview, returning a token up-front.
     The token expires in ~4 minutes so the second call must be immediate.)

Only ~36% of queries actually return an AI Overview — for the rest we return
an empty snapshot and let the caller fall back gracefully.

Docs: https://serpapi.com/google-ai-overview-api
"""
from typing import Optional
import httpx

from config import settings


SERPAPI_BASE = "https://serpapi.com/search.json"
SERPAPI_TIMEOUT = 45.0  # page_token flow can be slow


def _flatten_text_blocks(text_blocks: list[dict]) -> str:
    """Convert SerpAPI's text_blocks list into one readable paragraph string.

    Block types we know about: heading, paragraph, list, expandable, comparison.
    """
    out: list[str] = []
    for block in text_blocks or []:
        btype = block.get("type")
        if btype in ("paragraph", "heading"):
            snippet = block.get("snippet") or block.get("text") or ""
            if snippet:
                out.append(snippet.strip())
        elif btype == "list":
            for item in block.get("list", []):
                title = item.get("title")
                snippet = item.get("snippet", "")
                line = f"- {title}: {snippet}" if title else f"- {snippet}"
                out.append(line.strip())
        elif btype == "expandable":
            # Nested structure: { title, text_blocks: [...] }
            title = block.get("title")
            if title:
                out.append(title.strip())
            nested = _flatten_text_blocks(block.get("text_blocks", []))
            if nested:
                out.append(nested)
        elif btype == "comparison":
            # Table-ish — just dump any snippet we find
            snippet = block.get("snippet") or ""
            if snippet:
                out.append(snippet.strip())
        else:
            # Unknown type — grab any string-valued fields as a fallback
            for key in ("snippet", "text", "title"):
                val = block.get(key)
                if isinstance(val, str) and val.strip():
                    out.append(val.strip())
                    break
    return "\n\n".join(out).strip()


def _normalize_references(refs: list[dict]) -> list[dict]:
    """Strip SerpAPI reference objects down to {url, title, source}."""
    normalized = []
    for r in refs or []:
        url = r.get("link") or r.get("url")
        if not url:
            continue
        normalized.append({
            "url": url,
            "title": (r.get("title") or "").strip(),
            "source": (r.get("source") or "").strip(),
        })
    return normalized


def _extract_overview(data: dict) -> dict:
    """Pull the ai_overview section out of a SerpAPI response into our shape."""
    overview = data.get("ai_overview") or {}
    text_blocks = overview.get("text_blocks", [])
    references = overview.get("references", [])
    return {
        "was_returned": bool(text_blocks),
        "overview_text": _flatten_text_blocks(text_blocks),
        "text_blocks": text_blocks,
        "references": _normalize_references(references),
        "raw_response": data,
    }


def _empty(query: str) -> dict:
    return {
        "query": query,
        "was_returned": False,
        "overview_text": "",
        "text_blocks": [],
        "references": [],
        "raw_response": {},
    }


def fetch_ai_overview(query: str) -> dict:
    """
    Fetch the Google AI Overview for `query`. Returns a dict matching the
    AIOverviewSnapshot model fields. Never raises — all failures return
    an empty snapshot with was_returned=False.
    """
    if not settings.serpapi_api_key:
        print("[serp] SERPAPI_API_KEY not set — skipping AI Overview fetch")
        return _empty(query)

    try:
        with httpx.Client(timeout=SERPAPI_TIMEOUT) as client:
            # Step 1: regular Google search, see if AI Overview is inline
            resp = client.get(SERPAPI_BASE, params={
                "engine": "google",
                "q": query,
                "api_key": settings.serpapi_api_key,
                "hl": "en",
                "gl": "us",
            })
            resp.raise_for_status()
            data = resp.json()

            overview = data.get("ai_overview") or {}

            # Inline — we're done
            if overview.get("text_blocks"):
                result = _extract_overview(data)
                result["query"] = query
                return result

            # Deferred flow: follow the page_token immediately
            page_token = overview.get("page_token")
            if page_token:
                resp2 = client.get(SERPAPI_BASE, params={
                    "engine": "google_ai_overview",
                    "page_token": page_token,
                    "api_key": settings.serpapi_api_key,
                })
                resp2.raise_for_status()
                data2 = resp2.json()
                result = _extract_overview(data2)
                result["query"] = query
                return result

            # No AI Overview for this query at all (normal for ~64% of queries)
            out = _empty(query)
            out["raw_response"] = data
            return out

    except httpx.HTTPStatusError as e:
        print(f"[serp] HTTP {e.response.status_code} from SerpAPI: {e.response.text[:200]}")
        return _empty(query)
    except Exception as e:
        print(f"[serp] Unexpected error: {type(e).__name__}: {e}")
        return _empty(query)


def pick_primary_query(queries: list[str]) -> Optional[str]:
    """
    Pick which query to hit with SerpAPI. We want the most buyer-intent,
    category-level query — the first one from build_queries() is typically
    'What are the best {category} tools available right now?' which is ideal.
    """
    return queries[0] if queries else None
