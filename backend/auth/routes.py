from __future__ import annotations

from datetime import datetime, timedelta, timezone

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from pymongo.errors import DuplicateKeyError
from starlette.config import Config as StarletteConfig

from backend.auth import config
from backend.auth.database import get_users_collection
from backend.auth.security import (
    check_otp,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    make_otp,
    public_user,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SignupIn(BaseModel):
    email: EmailStr
    password: str
    name: str = ""


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class RefreshIn(BaseModel):
    refresh_token: str


class RequestCodeIn(BaseModel):
    email: EmailStr


class VerifyCodeIn(BaseModel):
    email: EmailStr
    code: str


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    email: EmailStr
    code: str
    new_password: str


# --- Google OAuth (Authlib + Starlette session) ---
_starlette_config = StarletteConfig(
    environ={
        "GOOGLE_CLIENT_ID": config.GOOGLE_CLIENT_ID,
        "GOOGLE_CLIENT_SECRET": config.GOOGLE_SECRET_KEY,
    }
)
oauth = OAuth(_starlette_config)
oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


@router.post("/signup", response_model=TokenOut)
def signup(body: SignupIn):
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be >= 6 chars")
    users = get_users_collection()
    email = body.email.lower().strip()
    if users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    doc = {
        "email": email,
        "name": body.name.strip(),
        "hashed_password": hash_password(body.password),
        "google_id": None,
        "email_verified": False,
        "created_at": datetime.now(timezone.utc),
    }
    try:
        result = users.insert_one(doc)
        doc["_id"] = result.inserted_id
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="Email already registered")
    return {
        "access_token": create_access_token(email),
        "refresh_token": create_refresh_token(email),
        "token_type": "bearer",
        "user": public_user(doc),
    }


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn):
    users = get_users_collection()
    email = body.email.lower().strip()
    doc = users.find_one({"email": email})
    if not doc or not doc.get("hashed_password"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not verify_password(body.password, doc["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return {
        "access_token": create_access_token(email),
        "refresh_token": create_refresh_token(email),
        "token_type": "bearer",
        "user": public_user(doc),
    }


@router.post("/refresh")
def refresh(body: RefreshIn):
    # Silent renewal: valid refresh token -> fresh pair (rotation).
    # Refresh itself expired/invalid -> 401 -> frontend must send user to login.
    email = decode_token(body.refresh_token, expected_type="refresh")
    users = get_users_collection()
    doc = users.find_one({"email": email})
    if not doc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return {
        "access_token": create_access_token(email),
        "refresh_token": create_refresh_token(email),
        "token_type": "bearer",
        "user": public_user(doc),
    }


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return {"user": user}


@router.post("/forgot-password")
async def forgot_password(body: ForgotIn):
    # Exact responses: 404 if no account, 400 if Google-only account.
    from backend.auth.emails import reset_email
    from backend.auth.mailer import send_mail

    users = get_users_collection()
    email = body.email.lower().strip()
    doc = users.find_one({"email": email})
    if not doc:
        raise HTTPException(status_code=404, detail="Account not found.")
    if not doc.get("hashed_password"):
        raise HTTPException(status_code=400, detail="This account uses Google sign-in. No password to reset.")
    now = datetime.now(timezone.utc)
    last = doc.get("reset_sent_at")
    if last is not None:
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if (now - last).total_seconds() < config.RESEND_COOLDOWN_SEC:
            return {"ok": True, "throttled": True, "email": email}
    code, digest = make_otp()
    expires = now + timedelta(seconds=config.OTP_EXPIRE_SEC)
    users.update_one(
        {"_id": doc["_id"]},
        {"$set": {"reset_hash": digest, "reset_expires": expires, "reset_sent_at": now}},
    )
    name = doc.get("name") or email.split("@")[0]
    subject, text, html = reset_email(name, code)
    try:
        await send_mail(email, subject, text, html)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not send email: {e}")
    return {"ok": True, "email": email, "expires_in": config.OTP_EXPIRE_SEC}


@router.post("/reset-password")
def reset_password(body: ResetIn):
    # Correct code -> new password saved + confirmation mail (best effort).
    from backend.auth.emails import password_changed_email
    from backend.auth.mailer import send_mail_sync

    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
    users = get_users_collection()
    email = body.email.lower().strip()
    doc = users.find_one({"email": email})
    if not doc:
        raise HTTPException(status_code=404, detail="Account not found.")
    digest = doc.get("reset_hash")
    expires = doc.get("reset_expires")
    if not digest or not expires:
        raise HTTPException(status_code=400, detail="No reset code requested. Tap resend first.")
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires:
        raise HTTPException(status_code=400, detail="Code expired. Request a new one.")
    if not check_otp(body.code, digest):
        raise HTTPException(status_code=400, detail="Wrong code. Check and try again.")
    if doc.get("hashed_password") and verify_password(body.new_password, doc["hashed_password"]):
        raise HTTPException(status_code=400, detail="Use a new password. This is your old one.")
    users.update_one(
        {"_id": doc["_id"]},
        {
            "$set": {"hashed_password": hash_password(body.new_password)},
            "$unset": {"reset_hash": "", "reset_expires": ""},
        },
    )
    name = doc.get("name") or email.split("@")[0]
    try:
        subject, text, html = password_changed_email(name, f"{config.FRONTEND_URL}/login")
        send_mail_sync(email, subject, text, html)
        mail_sent = True
    except Exception:
        mail_sent = False
    return {"ok": True, "email": email, "mail_sent": mail_sent}


@router.post("/request-code")
async def request_code(body: RequestCodeIn):
    # Generates a 6-digit code (valid OTP_EXPIRE_SEC) and mails it.
    # Called when the OTP modal opens and on every Resend.
    from backend.auth.emails import verification_email
    from backend.auth.mailer import send_mail

    users = get_users_collection()
    email = body.email.lower().strip()
    doc = users.find_one({"email": email})
    if not doc:
        raise HTTPException(status_code=404, detail="Account not found")
    if doc.get("email_verified"):
        return {"ok": True, "already_verified": True, "email": email}
    now = datetime.now(timezone.utc)
    last = doc.get("otp_sent_at")
    if last is not None:
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if (now - last).total_seconds() < config.RESEND_COOLDOWN_SEC:
            return {"ok": True, "throttled": True, "email": email}
    code, digest = make_otp()
    expires = now + timedelta(seconds=config.OTP_EXPIRE_SEC)
    users.update_one(
        {"_id": doc["_id"]},
        {"$set": {"otp_hash": digest, "otp_expires": expires, "otp_sent_at": now}},
    )
    name = doc.get("name") or email.split("@")[0]
    subject, text, html = verification_email(name, code)
    try:
        await send_mail(email, subject, text, html)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not send email: {e}")
    return {"ok": True, "email": email, "expires_in": config.OTP_EXPIRE_SEC}


@router.post("/verify-code")
def verify_code(body: VerifyCodeIn):
    # Correct code within time -> email_verified:true. Frontend then goes to /login.
    users = get_users_collection()
    email = body.email.lower().strip()
    doc = users.find_one({"email": email})
    if not doc:
        raise HTTPException(status_code=404, detail="Account not found")
    if doc.get("email_verified"):
        return {"ok": True, "already_verified": True, "email": email}
    digest = doc.get("otp_hash")
    expires = doc.get("otp_expires")
    if not digest or not expires:
        raise HTTPException(status_code=400, detail="No code requested. Tap Resend.")
    now = datetime.now(timezone.utc)
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if now > expires:
        raise HTTPException(status_code=400, detail="Code expired. Tap Resend for a new one.")
    if not check_otp(body.code, digest):
        raise HTTPException(status_code=400, detail="Wrong code. Check and try again.")
    users.update_one(
        {"_id": doc["_id"]},
        {"$set": {"email_verified": True}, "$unset": {"otp_hash": "", "otp_expires": ""}},
    )
    return {"ok": True, "email": email}


@router.get("/google/login")
async def google_login(request: Request):
    if not config.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="GOOGLE_CLIENT_ID missing in .env")
    return await oauth.google.authorize_redirect(request, config.GOOGLE_REDIRECT_URI)


@router.get("/google/callback")
async def google_callback(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Google auth failed: {e}")
    userinfo = token.get("userinfo") or await oauth.google.userinfo(token=token)
    email = (userinfo.get("email") or "").lower().strip()
    if not email:
        raise HTTPException(status_code=400, detail="Google did not return email")
    users = get_users_collection()
    doc = users.find_one({"email": email})
    if doc is None:
        doc = {
            "email": email,
            "name": userinfo.get("name", ""),
            "hashed_password": None,
            "google_id": userinfo.get("sub"),
            "email_verified": True,
            "created_at": datetime.now(timezone.utc),
        }
        result = users.insert_one(doc)
        doc["_id"] = result.inserted_id
    else:
        if not doc.get("google_id") and userinfo.get("sub"):
            users.update_one({"_id": doc["_id"]}, {"$set": {"google_id": userinfo.get("sub")}})
    jwt_token = create_access_token(email)
    refresh_token = create_refresh_token(email)
    # Connection point: backend -> frontend. Must match the /auth/callback
    # route in frontend/auth/AuthCallback.jsx which reads both from the URL.
    frontend_url = f"{config.FRONTEND_URL}/auth/callback#token={jwt_token}&refresh={refresh_token}"
    return RedirectResponse(url=frontend_url)
