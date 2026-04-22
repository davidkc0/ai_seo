"""
Cloudflare GraphQL Analytics adapter for AI bot traffic analysis.

Uses Cloudflare's Analytics API to query HTTP request logs filtered
by known AI bot user-agent strings. Works with Cloudflare's free plan
(GraphQL Analytics is available on all plans).

Cloudflare API Token must have "Analytics:Read" + "Zone:Read" permissions.
"""
import httpx
from datetime import datetime, timedelta, timezone
from typing import Optional


# ── Known AI bot user-agent substrings ─────────────────────────────────
# Each entry: (substring to match in UA, bot_name, platform, category)
AI_BOT_SIGNATURES = [
    # OpenAI
    ("GPTBot",           "GPTBot",           "openai",     "training"),
    ("OAI-SearchBot",    "OAI-SearchBot",    "openai",     "search"),
    ("ChatGPT-User",     "ChatGPT-User",     "openai",     "user_agent"),
    # Anthropic
    ("ClaudeBot",        "ClaudeBot",        "anthropic",  "training"),
    ("Claude-SearchBot", "Claude-SearchBot", "anthropic",  "search"),
    ("Claude-User",      "Claude-User",      "anthropic",  "user_agent"),
    ("claude-web",       "ClaudeBot",        "anthropic",  "training"),  # legacy
    ("anthropic-ai",     "ClaudeBot",        "anthropic",  "training"),  # legacy
    # Perplexity
    ("PerplexityBot",    "PerplexityBot",    "perplexity", "search"),
    ("Perplexity-User",  "Perplexity-User",  "perplexity", "user_agent"),
    # Google
    ("Google-Extended",  "Google-Extended",  "google",     "training"),
    ("Google-Agent",     "Google-Agent",     "google",     "user_agent"),
    # Meta
    ("Meta-ExternalAgent",   "Meta-ExternalAgent",   "meta", "training"),
    ("Meta-ExternalFetcher", "Meta-ExternalFetcher", "meta", "training"),
]

CF_GRAPHQL_URL = "https://api.cloudflare.com/client/v4/graphql"
CF_API_BASE = "https://api.cloudflare.com/client/v4"
CF_TIMEOUT = 30.0


def classify_user_agent(user_agent: str) -> Optional[dict]:
    """Match a user-agent string to a known AI bot. Returns None if no match."""
    for substring, bot_name, platform, category in AI_BOT_SIGNATURES:
        if substring in user_agent:
            return {
                "bot_name": bot_name,
                "bot_platform": platform,
                "bot_category": category,
            }
    return None


def verify_token(api_token: str) -> dict:
    """Verify a Cloudflare API token and return account info.

    Returns: {"valid": True/False, "error": str|None}
    """
    try:
        with httpx.Client(timeout=CF_TIMEOUT) as client:
            resp = client.get(
                f"{CF_API_BASE}/user/tokens/verify",
                headers={"Authorization": f"Bearer {api_token}"},
            )
            data = resp.json()
            if data.get("success") and data.get("result", {}).get("status") == "active":
                return {"valid": True, "error": None}
            return {"valid": False, "error": data.get("errors", [{}])[0].get("message", "Token invalid")}
    except Exception as e:
        return {"valid": False, "error": str(e)}


def list_zones(api_token: str) -> list[dict]:
    """List all zones (domains) accessible by this token.

    Returns: [{"id": "abc123", "name": "illusion.ai"}, ...]
    """
    try:
        with httpx.Client(timeout=CF_TIMEOUT) as client:
            resp = client.get(
                f"{CF_API_BASE}/zones",
                headers={"Authorization": f"Bearer {api_token}"},
                params={"per_page": 50, "status": "active"},
            )
            resp.raise_for_status()
            data = resp.json()
            return [
                {"id": z["id"], "name": z["name"]}
                for z in data.get("result", [])
            ]
    except Exception as e:
        print(f"[bot_analytics] Failed to list zones: {e}")
        return []


def fetch_bot_traffic(
    api_token: str,
    zone_id: str,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> list[dict]:
    """Fetch AI bot traffic from Cloudflare Analytics for a zone.

    Uses the httpRequestsAdaptiveGroups dataset which provides per-request
    user-agent data aggregated by path and UA string.

    Returns a list of bot visit dicts ready for DB insertion:
    [{"bot_name", "bot_platform", "bot_category", "path", "status_code",
      "request_count", "visited_at"}, ...]
    """
    if since is None:
        since = datetime.now(timezone.utc) - timedelta(days=1)
    if until is None:
        until = datetime.now(timezone.utc)

    # GraphQL query: aggregate requests by clientRequestPath and userAgent,
    # filtered to our known AI bot UA substrings.
    # We use httpRequestsAdaptiveGroups which has flexible filtering.
    query = """
    query BotTraffic($zoneTag: String!, $since: DateTime!, $until: DateTime!) {
      viewer {
        zones(filter: { zoneTag: $zoneTag }) {
          httpRequestsAdaptiveGroups(
            filter: {
              datetime_geq: $since
              datetime_lt: $until
              requestSource: "eyeball"
            }
            limit: 5000
            orderBy: [count_DESC]
          ) {
            count
            dimensions {
              clientRequestPath
              userAgent
              edgeResponseStatus
              datetime
            }
          }
        }
      }
    }
    """

    variables = {
        "zoneTag": zone_id,
        "since": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "until": until.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    try:
        with httpx.Client(timeout=CF_TIMEOUT) as client:
            resp = client.post(
                CF_GRAPHQL_URL,
                headers={
                    "Authorization": f"Bearer {api_token}",
                    "Content-Type": "application/json",
                },
                json={"query": query, "variables": variables},
            )
            resp.raise_for_status()
            data = resp.json()

        zones = data.get("data", {}).get("viewer", {}).get("zones", [])
        if not zones:
            print(f"[bot_analytics] No zone data returned for {zone_id}")
            return []

        groups = zones[0].get("httpRequestsAdaptiveGroups", [])
        bot_visits = []

        for group in groups:
            dims = group.get("dimensions", {})
            ua = dims.get("userAgent", "")
            classification = classify_user_agent(ua)

            if classification is None:
                continue  # Not an AI bot, skip

            count = group.get("count", 1)
            path = dims.get("clientRequestPath", "/")
            status = dims.get("edgeResponseStatus")
            dt_str = dims.get("datetime")

            visited_at = datetime.now(timezone.utc)
            if dt_str:
                try:
                    visited_at = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

            bot_visits.append({
                **classification,
                "path": path,
                "status_code": status,
                "request_count": count,
                "visited_at": visited_at,
            })

        print(f"[bot_analytics] Found {len(bot_visits)} AI bot visit groups for zone {zone_id}")
        return bot_visits

    except httpx.HTTPStatusError as e:
        print(f"[bot_analytics] Cloudflare HTTP {e.response.status_code}: {e.response.text[:200]}")
        return []
    except Exception as e:
        print(f"[bot_analytics] Error fetching bot traffic: {type(e).__name__}: {e}")
        return []
