"""QuestAI branded auth emails — one layout, event-specific content.

Layout: header (logo + product) / heading / greeting / body / CTA / expiry /
footer (agents, reason, copyright, links). Dark theme matching the landing page.
Table-based + inline styles for maximum email-client compatibility.
"""
from __future__ import annotations

import html

PRODUCT = "QuestAI"
LOGO_URL = "https://plain-apac-prod-public.komododecks.com/202609/25/Vks3Yyo4JP6b6VuUr1UW/image.png"
ACCENT = "#4f46e5"
BG = "#f4f5f7"
CARD = "#ffffff"
TEXT = "#111827"
MUTED = "#6b7280"
LINE = "#e5e7eb"
YEAR = "2026"


def base_email(
    heading: str,
    name: str,
    body_html: str,
    cta_text: str | None = None,
    cta_url: str | None = None,
    expiry_note: str | None = None,
    footer_reason: str = "You received this email because you have a QuestAI account.",
) -> str:
    cta = ""
    if cta_text and cta_url:
        cta = f"""
        <tr><td align="center" style="padding: 8px 0 8px 0;">
          <a href="{cta_url}" style="display: inline-block; background: {ACCENT}; color: #ffffff;
            font-weight: 700; font-size: 15px; text-decoration: none;
            padding: 13px 34px; border-radius: 10px;">{cta_text}</a>
        </td></tr>"""
    expiry = (
        f'<tr><td align="center" style="color: {MUTED}; font-size: 13px; padding: 6px 0 0 0;">{expiry_note}</td></tr>'
        if expiry_note
        else ""
    )
    return f"""<!doctype html>
<html><body style="margin: 0; padding: 0; background: {BG};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background: {BG}; padding: 32px 12px;">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0"
  style="max-width: 600px; width: 100%; background: {CARD}; border: 1px solid {LINE};
  border-radius: 18px; overflow: hidden; font-family: Arial, Helvetica, sans-serif; color: {TEXT};">
  <tr><td align="center" style="padding: 28px 24px 4px 24px;">
    <img src="{LOGO_URL}" alt="{PRODUCT}" width="140" style="display: block; border: 0;" />
  </td></tr>
  <tr><td align="center" style="font-size: 20px; font-weight: 700; color: {TEXT}; padding: 14px 24px 2px 24px;">{html.escape(heading)}</td></tr>
  <tr><td style="font-size: 14px; line-height: 1.7; color: {TEXT}; padding: 10px 32px 0 32px;">
    <p style="margin: 0 0 10px 0;">Hi {html.escape(name)},</p>
    {body_html}
  </td></tr>
  {cta}
  {expiry}
  <tr><td align="center" style="color: {MUTED}; font-size: 12px; padding: 22px 24px 0 24px;">
    Research &bull; Travel &bull; Shopping &bull; Jobs
  </td></tr>
  <tr><td align="center" style="color: {MUTED}; font-size: 12px; padding: 6px 32px 0 32px;">{footer_reason}</td></tr>
  <tr><td align="center" style="color: {MUTED}; font-size: 12px; padding: 12px 24px 28px 24px;">
    &copy; {YEAR} {PRODUCT} &nbsp;&middot;&nbsp; Privacy &nbsp;&middot;&nbsp; Terms &nbsp;&middot;&nbsp; Support
  </td></tr>
</table>
</td></tr>
</table>
</body></html>"""


def _p(text: str) -> str:
    return f'<p style="margin: 0 0 12px 0;">{text}</p>'


# --- 1. Welcome + verification (6-digit code) ---
def verification_email(name: str, code: str) -> tuple[str, str, str]:
    subject = f"Welcome to {PRODUCT} — Verify your email"
    code_html = (
        f"<p style='text-align: center; font-size: 28px; font-weight: 400; "
        f"letter-spacing: 6px; margin: 16px 0; color: {TEXT};'>{code}</p>"
    )
    body = _p("Your account is almost ready.") + _p(
        "Enter this 6-digit code on the verification screen to activate your account:"
    ) + code_html
    html = base_email(
        heading=f"Welcome to {PRODUCT}",
        name=name,
        body_html=body,
        expiry_note="This code expires in 10 minutes. If it expires, request a new one.",
        footer_reason="You received this email because you created a QuestAI account. "
        "If that wasn't you, safely ignore it.",
    )
    text = (
        f"Hi {name},\n\nYour account is almost ready.\n"
        f"Your verification code is: {code}\n\nIt expires in 10 minutes.\n"
        "If you didn't create this account, ignore this email."
    )
    return subject, text, html


# --- 2. Forgot password (6-digit code) ---
def reset_email(name: str, code: str) -> tuple[str, str, str]:
    subject = f"Reset your {PRODUCT} password"
    code_html = (
        f"<p style='text-align: center; font-size: 28px; font-weight: 400; "
        f"letter-spacing: 6px; margin: 16px 0; color: {TEXT};'>{code}</p>"
    )
    body = _p(f"We received a request to reset the password for your {PRODUCT} account.") + _p(
        "Enter this 6-digit code on the reset screen along with your new password:"
    ) + code_html
    html = base_email(
        heading="Reset your password",
        name=name,
        body_html=body,
        expiry_note="This code expires in 10 minutes.",
        footer_reason="If you didn't request a password reset, ignore this email. "
        "Your password will remain unchanged.",
    )
    text = (
        f"Hi {name},\n\nWe received a request to reset your {PRODUCT} password.\n"
        f"Your reset code is: {code}\n\nIt expires in 10 minutes.\n"
        "If you didn't request it, ignore this email."
    )
    return subject, text, html


# --- 3. Password changed ---
def password_changed_email(name: str, secure_url: str) -> tuple[str, str, str]:
    subject = f"Your {PRODUCT} password was changed"
    body = _p(f"Your {PRODUCT} password was successfully changed.") + _p(
        "If you made this change, no further action is required."
    )
    html = base_email(
        heading="Password changed successfully",
        name=name,
        body_html=body,
        cta_text="Secure My Account &rarr;",
        cta_url=secure_url,
        footer_reason="If you didn't change your password, secure your account immediately.",
    )
    text = (
        f"Hi {name},\n\nYour {PRODUCT} password was successfully changed.\n"
        "If you made this change, no action is needed.\n"
        f"If not, secure your account: {secure_url}"
    )
    return subject, text, html


# --- 4. Welcome after verification ---
def welcome_email(name: str, start_url: str) -> tuple[str, str, str]:
    subject = f"You're all set — welcome to {PRODUCT}"
    body = (
        _p("Your email has been verified and your account is ready.")
        + _p(f"With {PRODUCT}, you can explore:")
        + "<ul style='margin: 0 0 12px 0; padding-left: 20px;'>"
        "<li><b>Research</b> — Investigate topics with AI-powered research</li>"
        "<li><b>Travel</b> — Search and plan trips</li>"
        "<li><b>Shopping</b> — Compare products and prices</li>"
        "<li><b>Jobs</b> — Discover relevant opportunities</li>"
        "</ul>"
        + _p("Research it. Plan it. Compare it. Find it.")
    )
    html = base_email(
        heading="You're in. Welcome aboard.",
        name=name,
        body_html=body,
        cta_text="Start Exploring &rarr;",
        cta_url=start_url,
        footer_reason="You received this email because you verified your QuestAI account.",
    )
    text = (
        f"Hi {name},\n\nYour email is verified and your account is ready.\n"
        "Explore: Research, Travel, Shopping, Jobs.\n"
        f"Start here: {start_url}\n\nResearch it. Plan it. Compare it. Find it."
    )
    return subject, text, html
