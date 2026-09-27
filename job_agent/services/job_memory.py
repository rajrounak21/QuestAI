from __future__ import annotations

import hashlib
import time
from typing import Any

# Simple in-memory session for job discovery phase 1
# Keeps skills/profile from first resume so secondary inline search reuses them without re-upload

_sessions: dict[str, dict[str, Any]] = {}
_TTL_SEC = 30 * 60  # 30 minutes

def _hash_bytes(b: bytes | None) -> str | None:
    if not b:
        return None
    return hashlib.md5(b).hexdigest()[:12]

def get_session(session_id: str) -> dict[str, Any] | None:
    sess = _sessions.get(session_id)
    if not sess:
        return None
    if time.time() - sess.get("_ts", 0) > _TTL_SEC:
        _sessions.pop(session_id, None)
        return None
    return sess

def save_session(session_id: str, profile: dict[str, Any] | None, resume_bytes: bytes | None = None, resume_text: str | None = None):
    if not session_id:
        return
    sess = _sessions.get(session_id, {})
    sess["_ts"] = time.time()
    if profile:
        sess["skills"] = list(profile.get("skills") or [])
        sess["target_roles"] = list(profile.get("target_roles") or [])
        sess["locations"] = list(profile.get("locations") or [])
        sess["work_mode"] = list(profile.get("work_mode") or [])
        sess["projects"] = list(profile.get("projects") or [])
        sess["education"] = list(profile.get("education") or [])
        sess["experience"] = list(profile.get("experience") or [])
        sess["name"] = profile.get("name")
        sess["links"] = list(profile.get("links") or [])
        if resume_text:
            sess["resume_text"] = resume_text[:8000]
        elif profile.get("raw_text"):
            sess["resume_text"] = profile.get("raw_text", "")[:8000]
        sess["profile"] = profile
    if resume_bytes:
        sess["resume_hash"] = _hash_bytes(resume_bytes)
    _sessions[session_id] = sess

def get_profile_memory(session_id: str) -> dict[str, Any] | None:
    sess = get_session(session_id)
    if not sess:
        return None
    return sess.get("profile")
