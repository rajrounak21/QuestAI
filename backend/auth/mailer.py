from __future__ import annotations

import os

import aiosmtplib
from dotenv import load_dotenv
from email.message import EmailMessage

from backend.auth import config

load_dotenv(override=True)

SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
MAIL_FROM: str = os.getenv("MAIL_FROM", SMTP_USERNAME or "noreply@questai.app")


def _build_message(to: str, subject: str, text: str, html: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = MAIL_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    return msg


async def send_mail(to: str, subject: str, text: str, html: str) -> None:
    # Routes gate on MAIL_ENABLED first; this stops any bypass.
    if not config.MAIL_ENABLED:
        raise RuntimeError("MAIL_ENABLED is false — email delivery is disabled.")
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        raise RuntimeError("SMTP_USERNAME / SMTP_PASSWORD missing in .env")
    # Gmail shows app passwords as "xxxx xxxx xxxx xxxx" — SMTP needs them spaceless.
    password = SMTP_PASSWORD.replace(" ", "")
    msg = _build_message(to, subject, text, html)
    await aiosmtplib.send(
        msg,
        hostname=SMTP_HOST,
        port=SMTP_PORT,
        username=SMTP_USERNAME,
        password=password,
        start_tls=True,
    )


def send_mail_sync(to: str, subject: str, text: str, html: str) -> None:
    import asyncio

    asyncio.run(send_mail(to, subject, text, html))
