from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv(override=True)

MONGODB_URI: str = os.getenv("MONGODB_URI", "")
JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MIN: int = int(os.getenv("JWT_EXPIRE_MIN", "60"))
REFRESH_EXPIRE_DAYS: int = int(os.getenv("REFRESH_EXPIRE_DAYS", "7"))
OTP_EXPIRE_SEC: int = int(os.getenv("OTP_EXPIRE_SEC", "600"))
RESEND_COOLDOWN_SEC: int = int(os.getenv("RESEND_COOLDOWN_SEC", "30"))

# Master switch for all email. false = no sends, no verify prompt.
MAIL_ENABLED: bool = os.getenv("MAIL_ENABLED", "false").strip().lower() in ("true", "1", "yes")

GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_SECRET_KEY: str = os.getenv("GOOGLE_SECRET_KEY", "")
GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", "")

AUTH_PORT: int = int(os.getenv("AUTH_PORT", "8000"))

FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

# Extra browser origins allowed by CORS, comma-separated. Needed when the
# frontend is served from a tunnel (ngrok) or any other non-localhost host,
# since the built-in list only covers localhost. FRONTEND_URL is allowed too.
EXTRA_CORS_ORIGINS: str = os.getenv("EXTRA_CORS_ORIGINS", "")

# Shared secret for the n8n scheduler. The alert endpoints that a machine calls
# (/alerts/due, /alerts/{id}/run) take this in an X-Service-Key header instead of
# a user JWT, because n8n is not a logged-in user. It must never reach the
# frontend bundle - it lives only in .env and in n8n's own credentials.
N8N_SERVICE_KEY: str = os.getenv("N8N_SERVICE_KEY", "")
