from __future__ import annotations

import re


def classify_freshness(posted_at: str | None, extensions: list[str] | None = None) -> str:
    """Classify posted_at label into buckets. Source truth preserved."""
    raw = (posted_at or "").strip().lower()
    # fallback to extensions if posted_at empty
    if not raw and extensions:
        for ext in extensions:
            low = ext.lower()
            if "hour" in low or "day" in low or "week" in low or "today" in low or "yesterday" in low or "ago" in low:
                raw = low
                break
    if not raw:
        return "Unknown"
    if "today" in raw or "just posted" in raw or "hour" in raw:
        return "Today"
    # parse "X days ago"
    m = re.search(r"(\d+)\s*day", raw)
    if m:
        try:
            n = int(m.group(1))
            if n <= 1:
                return "1 day ago"
            if n <= 3:
                return "3 days ago"
            if n <= 7:
                return "1 week ago"
            return "Older"
        except ValueError:
            pass
    if "yesterday" in raw:
        return "1 day ago"
    if "week" in raw:
        return "1 week ago"
    if "month" in raw:
        return "Older"
    return "Unknown"


_FRESHNESS_ORDER = {"Today": 0, "1 day ago": 1, "3 days ago": 2, "1 week ago": 3, "Older": 4, "Unknown": 5}


def freshness_sort_key(bucket: str) -> int:
    return _FRESHNESS_ORDER.get(bucket, 5)
