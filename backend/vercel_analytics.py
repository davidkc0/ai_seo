"""
Vercel API adapter for AI bot traffic analysis via Log Drains.

Unlike Cloudflare (pull-based GraphQL), Vercel uses a push-based model:
we register a Log Drain webhook and Vercel streams request logs to us
in real-time. Each log includes proxy.userAgent and proxy.path.

Requires Vercel Pro or Enterprise plan (Log Drains unavailable on Hobby).
"""
import secrets
import httpx
from datetime import datetime, timezone
from typing import Optional

from bot_analytics import classify_user_agent  # shared UA classification

VERCEL_API_BASE = "https://api.vercel.com"
VERCEL_TIMEOUT = 30.0


def verify_token(api_token: str) -> dict:
    """Verify a Vercel API token by fetching the user profile.

    Returns: {"valid": True/False, "error": str|None, "user": dict|None}
    """
    try:
        with httpx.Client(timeout=VERCEL_TIMEOUT) as client:
            resp = client.get(
                f"{VERCEL_API_BASE}/v2/user",
                headers={"Authorization": f"Bearer {api_token}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                user = data.get("user", {})
                return {
                    "valid": True,
                    "error": None,
                    "user": {
                        "username": user.get("username"),
                        "email": user.get("email"),
                    },
                }
            elif resp.status_code == 403:
                return {"valid": False, "error": "Token is invalid or expired", "user": None}
            else:
                return {"valid": False, "error": f"Vercel API returned {resp.status_code}", "user": None}
    except Exception as e:
        return {"valid": False, "error": str(e), "user": None}


def list_projects(api_token: str) -> list[dict]:
    """List all projects accessible by this token.

    Returns: [{"id": "prj_abc", "name": "my-app", "framework": "nextjs"}, ...]
    """
    try:
        with httpx.Client(timeout=VERCEL_TIMEOUT) as client:
            resp = client.get(
                f"{VERCEL_API_BASE}/v9/projects",
                headers={"Authorization": f"Bearer {api_token}"},
                params={"limit": 50},
            )
            resp.raise_for_status()
            data = resp.json()
            return [
                {
                    "id": p["id"],
                    "name": p.get("name", "Unknown"),
                    "framework": p.get("framework"),
                }
                for p in data.get("projects", [])
            ]
    except Exception as e:
        print(f"[vercel_analytics] Failed to list projects: {e}")
        return []


def register_drain(
    api_token: str,
    project_id: str,
    webhook_url: str,
    webhook_secret: str,
) -> dict:
    """Register a Log Drain on a Vercel project pointing at our webhook.

    Returns: {"success": True, "drain_id": "...", "error": None}
    """
    try:
        with httpx.Client(timeout=VERCEL_TIMEOUT) as client:
            resp = client.post(
                f"{VERCEL_API_BASE}/v1/log-drains",
                headers={
                    "Authorization": f"Bearer {api_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "name": f"Illusion Bot Analytics",
                    "type": "json",
                    "url": webhook_url,
                    "projectIds": [project_id],
                    "sources": ["static", "edge", "lambda"],
                    "environments": ["production"],
                    "secret": webhook_secret,
                    "schemas": {"log": {"version": "v1"}},
                },
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                return {
                    "success": True,
                    "drain_id": data.get("id"),
                    "error": None,
                }
            else:
                error_text = resp.text[:300]
                print(f"[vercel_analytics] Failed to register drain: {resp.status_code} {error_text}")
                return {
                    "success": False,
                    "drain_id": None,
                    "error": f"Vercel returned {resp.status_code}: {error_text}",
                }
    except Exception as e:
        return {"success": False, "drain_id": None, "error": str(e)}


def delete_drain(api_token: str, drain_id: str) -> bool:
    """Delete a Log Drain from Vercel. Returns True on success."""
    try:
        with httpx.Client(timeout=VERCEL_TIMEOUT) as client:
            resp = client.delete(
                f"{VERCEL_API_BASE}/v1/log-drains/{drain_id}",
                headers={"Authorization": f"Bearer {api_token}"},
            )
            return resp.status_code in (200, 204, 404)  # 404 = already gone
    except Exception as e:
        print(f"[vercel_analytics] Failed to delete drain {drain_id}: {e}")
        return False


def generate_webhook_secret() -> str:
    """Generate a random secret for HMAC verification of incoming drain payloads."""
    return secrets.token_hex(32)


def parse_log_entry(entry: dict) -> Optional[dict]:
    """Parse a single Vercel log drain entry and classify the user agent.

    Vercel log entries have a `proxy` object with:
      proxy.userAgent (array of strings), proxy.path, proxy.statusCode, proxy.timestamp

    Returns a bot visit dict if the UA matches a known AI bot, else None.
    """
    proxy = entry.get("proxy")
    if not proxy:
        return None

    # proxy.userAgent is an array of strings
    user_agents = proxy.get("userAgent", [])
    if isinstance(user_agents, str):
        user_agents = [user_agents]

    for ua in user_agents:
        classification = classify_user_agent(ua)
        if classification:
            # Parse timestamp
            ts = proxy.get("timestamp")
            visited_at = datetime.now(timezone.utc)
            if ts:
                try:
                    if isinstance(ts, (int, float)):
                        visited_at = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
                    else:
                        visited_at = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                except (ValueError, TypeError, OSError):
                    pass

            return {
                **classification,
                "path": proxy.get("path", "/"),
                "status_code": proxy.get("statusCode") or entry.get("statusCode"),
                "request_count": 1,
                "visited_at": visited_at,
            }

    return None
