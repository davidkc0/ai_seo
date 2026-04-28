"""Shared slowapi limiter instance.

Lives in its own module so routers can `from rate_limit import limiter` without
creating a circular import against main.py (which imports the routers at
app-construction time).

In-memory storage is fine for single-instance Railway. Moving to multiple
backend instances would require a shared store (Redis) — slowapi supports it
via Limiter(key_func=..., storage_uri="redis://...").
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# Key by client IP. slowapi pulls X-Forwarded-For when running behind a proxy
# (Railway sets this), so this works correctly in production.
limiter = Limiter(key_func=get_remote_address)
