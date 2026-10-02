from __future__ import annotations

from typing import Any

# The uploaded resume PDF, in GridFS, for preview on the profile panel.
#
# Exactly ONE file per user. Uploading a new resume REPLACES the old one
# (delete-then-put), it is never appended — otherwise every re-upload would
# leave an orphaned copy behind and bloat the bucket.
#
# gridfs ships with pymongo, so this needs no extra dependency.

BUCKET = "job_resumes"


def _bucket():
    # GridFS has no `bucket` kwarg — the bucket is the first positional arg.
    from gridfs import GridFS
    from backend.database.mongodb import get_db

    return GridFS(get_db(), BUCKET)


def _existing_ids(user_id: str) -> list[Any]:
    """ObjectIds of every stored resume for this user (oldest first)."""
    from backend.database.mongodb import get_db

    docs = get_db()[BUCKET + ".files"].find(
        {"metadata.user_id": user_id}, {"_id": 1}
    ).sort("uploadDate", 1)
    return [d["_id"] for d in docs]


def save_resume_pdf(user_id: str, content: bytes, filename: str | None = None) -> Any:
    """Store the PDF, replacing any previously stored resume for this user."""
    fs = _bucket()
    # Replace, never append.
    delete_resume_pdf(user_id)
    return fs.put(
        content,
        filename=filename or "resume.pdf",
        metadata={"user_id": user_id},
    )


def get_resume_pdf(user_id: str) -> bytes | None:
    """Most recent stored PDF bytes, or None when the user has none."""
    fs = _bucket()
    ids = _existing_ids(user_id)
    if not ids:
        return None
    try:
        return fs.get(ids[-1]).read()
    except Exception:
        return None


def has_resume_pdf(user_id: str) -> bool:
    return bool(_existing_ids(user_id))


def delete_resume_pdf(user_id: str) -> bool:
    """Remove the stored resume. Returns True when a file was deleted."""
    fs = _bucket()
    ids = _existing_ids(user_id)
    if not ids:
        return False
    deleted = False
    for file_id in ids:
        try:
            fs.delete(file_id)
            deleted = True
        except Exception:
            continue
    return deleted
