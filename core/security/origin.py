"""
Browser origin policy for the local Kora API.

Only the Studio page itself (same loopback host:port as the request) and any
origins listed in KORA's `allowed_origins` setting may drive the API from a browser.
Requests without an Origin header (CLI, scripts, same-origin GETs) are unaffected.
"""

import re
from typing import List, Optional
from urllib.parse import urlsplit

from core.config import settings

LOOPBACK_ORIGIN = re.compile(r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$")


def extra_origins() -> List[str]:
    return [o.strip().rstrip("/") for o in settings.allowed_origins.split(",") if o.strip()]


def origin_allowed(origin: Optional[str], host: Optional[str]) -> bool:
    if origin is None:
        return True
    if origin in extra_origins():
        return True
    return bool(LOOPBACK_ORIGIN.fullmatch(origin)) and host is not None and urlsplit(origin).netloc == host
