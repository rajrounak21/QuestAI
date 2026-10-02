from __future__ import annotations

import hmac
import logging
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from backend.auth import config
from backend.auth.database import get_users_collection

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=config.JWT_EXPIRE_MIN)
    payload = {"sub": subject, "type": "access", "exp": expire}
    return jwt.encode(payload, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def create_refresh_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=config.REFRESH_EXPIRE_DAYS)
    payload = {"sub": subject, "type": "refresh", "exp": expire}
    return jwt.encode(payload, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def make_otp() -> tuple[str, str]:
    # 6-digit code + sha256 hash. Plain code goes to email only, hash to Mongo.
    import hashlib
    import secrets

    code = f"{secrets.randbelow(900000) + 100000}"
    digest = hashlib.sha256(code.encode()).hexdigest()
    return code, digest


def check_otp(code: str, digest: str) -> bool:
    import hashlib

    return hashlib.sha256(code.strip().encode()).hexdigest() == digest


def decode_token(token: str, expected_type: str = "access") -> str:
    try:
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
        email: str | None = payload.get("sub")
        if not email:
            raise JWTError("missing sub")
        if payload.get("type", "access") != expected_type:
            raise JWTError(f"wrong token type (expected {expected_type})")
        return email
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}")


def public_user(doc: dict) -> dict:
    return {
        "id": str(doc.get("_id")),
        "email": doc.get("email"),
        "name": doc.get("name"),
        "google_id": doc.get("google_id"),
        "email_verified": bool(doc.get("email_verified", False)),
        "created_at": str(doc.get("created_at")),
    }


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    email = decode_token(creds.credentials)
    users = get_users_collection()
    doc = users.find_one({"email": email})
    if not doc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return public_user(doc)


def require_service_key(
    x_service_key: str | None = Header(None, alias="X-Service-Key"),
) -> None:
    """Auth for machine callers (the n8n scheduler), not users.

    The alert endpoints n8n polls have no logged-in user, so a user JWT is not an
    option there. Instead they present a shared secret in X-Service-Key. This
    never grants access to user data endpoints — only to the two alert routes
    that are decorated with this dependency.

    Compared with hmac.compare_digest so the key cannot be recovered by timing
    the comparison character by character.
    """
    configured = config.N8N_SERVICE_KEY
    if not configured:
        # Fail closed: if the operator never set the key, nothing may call in.
        logger.error("N8N_SERVICE_KEY is not configured; rejecting service call")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service key not configured on the server",
        )
    if not x_service_key or not hmac.compare_digest(x_service_key, configured):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid service key")
