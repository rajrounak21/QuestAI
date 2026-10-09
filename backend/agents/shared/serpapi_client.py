"""The single SerpApi entry point for every non-jobs agent.

There used to be five independent module-level `_get_client()` singletons, one
per tool module, which meant the retry policy was whatever each module happened
to implement. This module is the one place a search is issued.

Jobs keeps its own client on purpose - that section is out of scope for this
change, so its searches do not go through here.
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from typing import Any

import serpapi
from dotenv import load_dotenv

load_dotenv(override=True)

logger = logging.getLogger(__name__)

_client: serpapi.Client | None = None
_client_lock = threading.Lock()


def _get_client() -> serpapi.Client:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                api_key = os.getenv("SERP_API_KEY")
                if not api_key:
                    raise ValueError("SERP_API_KEY not found in environment")
                _client = serpapi.Client(api_key=api_key)
    return _client


# SerpApi blips (503/429/5xx/timeout) are transient. A single retry recovers
# almost all of them, and without it one blip permanently deletes that result:
# destination research fans out 5 searches and merely logs the failure, so the
# itinerary is silently built on whatever evidence happened to survive.
#
# 4xx is NOT retried - a 400 means the request itself is wrong, so retrying
# burns a credit to fail identically.
_TRANSIENT = ("429", "500", "502", "503", "504", "timeout", "timed out", "connection reset")
_MAX_ATTEMPTS = 2
_BACKOFF_SECONDS = 1.5


def _is_transient(exc: Exception) -> bool:
    text = str(exc).lower()
    if "400" in text or "bad request" in text:
        return False
    return any(marker in text for marker in _TRANSIENT)


def _redact(exc: Exception) -> str:
    """Exception text with the API key removed.

    serpapi puts the full request URL, key included, in its error messages. Any
    log line or crash trace carrying that leaks the key in plain text.
    """
    text = str(exc)
    key = os.getenv("SERP_API_KEY") or ""
    if key:
        text = text.replace(key, "***")
    return re.sub(r"(api[_-]?key=)[^\s&'\"]+", r"\1***", text, flags=re.I)


def search(params: dict[str, Any]) -> Any:
    """Issue one SerpApi search, retrying a transient provider error once.

    `params` must carry "engine". Returns the serpapi response object so
    callers keep using `.data` exactly as they did before.
    """
    engine = str(params.get("engine") or "unknown")
    last: Exception | None = None

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            results = _get_client().search(params)
        except Exception as e:
            last = e
            if attempt < _MAX_ATTEMPTS and _is_transient(e):
                logger.warning(
                    "SerpApi %s blip (%s), retrying once", engine, _redact(e)[:80]
                )
                time.sleep(_BACKOFF_SECONDS)
                continue
            raise
        else:
            return results

    raise last if last else RuntimeError("SerpApi search failed")