"""Tiny static blocklist of throwaway / temporary email providers.

Cheap belt-and-suspenders alongside Turnstile + email verification —
catches scripts that hit /register before the captcha widget loads.

Keep the list short and well-known. Maintaining a comprehensive list is a
losing battle (new domains pop up daily); we just want to deter the most
obvious tourist traffic. Real anti-fraud lift comes from email verification.
"""

DISPOSABLE_DOMAINS = frozenset({
    "mailinator.com",
    "guerrillamail.com",
    "guerrillamail.net",
    "tempmail.com",
    "10minutemail.com",
    "10minutemail.net",
    "yopmail.com",
    "trashmail.com",
    "throwawaymail.com",
    "fakeinbox.com",
    "getnada.com",
    "dispostable.com",
    "maildrop.cc",
    "sharklasers.com",
    "spam4.me",
    "tempr.email",
    "tmpmail.org",
    "mintemail.com",
    "moakt.com",
    "tmail.ws",
})


def is_disposable(email: str) -> bool:
    """Return True if the email's domain is on the blocklist. Case-insensitive."""
    if not email or "@" not in email:
        return False
    domain = email.lower().rsplit("@", 1)[-1].strip()
    return domain in DISPOSABLE_DOMAINS
