from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

MONGODB_URI: str = os.getenv("MONGODB_URI", "")
JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MIN: int = int(os.getenv("JWT_EXPIRE_MIN", ""))
REFRESH_EXPIRE_DAYS: int = int(os.getenv("REFRESH_EXPIRE_DAYS", "7"))
OTP_EXPIRE_SEC: int = int(os.getenv("OTP_EXPIRE_SEC", "600"))
RESEND_COOLDOWN_SEC: int = int(os.getenv("RESEND_COOLDOWN_SEC", "30"))

GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_SECRET_KEY: str = os.getenv("GOOGLE_SECRET_KEY", "")
GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", "")

AUTH_PORT: int = int(os.getenv("AUTH_PORT", ""))

FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
