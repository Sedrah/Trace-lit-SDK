"""
Email sender for magic-link auth.

Priority:
  1. Resend API  (TRACELIT_RESEND_API_KEY set)      — recommended for production
  2. SMTP        (TRACELIT_SMTP_HOST set)            — self-hosted / air-gapped
  3. Log to stdout                                    — dev / air-gapped fallback

Resend setup (free tier, 100 emails/day):
  1. resend.com → create account → get API key
  2. Add a verified domain (or use onboarding@resend.dev for testing)
  3. Set TRACELIT_RESEND_API_KEY=re_xxx in .env
  4. Set TRACELIT_EMAIL_FROM=noreply@yourdomain.com
"""
from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage

logger = logging.getLogger("trace_lit.api")

_MAGIC_LINK_SUBJECT = "Your Trace-lit sign-in link"
_MAGIC_LINK_BODY    = """\
Hi,

Click the link below to sign in to Trace-lit:

  {url}

This link expires in 15 minutes and can only be used once.

If you didn't request this, you can ignore this email.

— Trace-lit
"""


def send_verification_email(to_email: str, verify_url: str) -> None:
    """Send a magic-link email. Never raises — failures are logged and fallen back."""
    resend_key = os.getenv("TRACELIT_RESEND_API_KEY", "")
    smtp_host  = os.getenv("TRACELIT_SMTP_HOST", "")

    if resend_key:
        _send_resend(to_email, verify_url, resend_key)
    elif smtp_host:
        _send_smtp(to_email, verify_url, smtp_host)
    else:
        _log_link(to_email, verify_url)


# ---------------------------------------------------------------------------
# Senders
# ---------------------------------------------------------------------------

def _send_resend(to_email: str, verify_url: str, api_key: str) -> None:
    import urllib.request, json as _json
    from_addr = os.getenv("TRACELIT_EMAIL_FROM", "onboarding@resend.dev")
    payload   = _json.dumps({
        "from":    from_addr,
        "to":      [to_email],
        "subject": _MAGIC_LINK_SUBJECT,
        "text":    _MAGIC_LINK_BODY.format(url=verify_url),
    }).encode()
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            logger.info("Magic link sent via Resend to %s (status %s)", to_email, resp.status)
    except Exception as exc:
        logger.error("Resend failed for %s: %s — falling back to log", to_email, exc)
        _log_link(to_email, verify_url)


def _send_smtp(to_email: str, verify_url: str, smtp_host: str) -> None:
    smtp_port = int(os.getenv("TRACELIT_SMTP_PORT", "587"))
    smtp_user = os.getenv("TRACELIT_SMTP_USER", "")
    smtp_pass = os.getenv("TRACELIT_SMTP_PASS", "")
    from_addr = os.getenv("TRACELIT_EMAIL_FROM", smtp_user or "noreply@trace-lit.com")

    msg             = EmailMessage()
    msg["Subject"]  = _MAGIC_LINK_SUBJECT
    msg["From"]     = from_addr
    msg["To"]       = to_email
    msg.set_content(_MAGIC_LINK_BODY.format(url=verify_url))

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls(context=ctx)
            if smtp_user:
                server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        logger.info("Magic link sent via SMTP to %s", to_email)
    except Exception as exc:
        logger.error("SMTP failed for %s: %s — falling back to log", to_email, exc)
        _log_link(to_email, verify_url)


def _log_link(to_email: str, verify_url: str) -> None:
    """Dev/air-gapped fallback — print to stdout so admin can relay the link."""
    logger.info("Magic link for %s: %s", to_email, verify_url)
    print(f"\n[Trace-lit] Sign-in link for {to_email}:\n  {verify_url}\n", flush=True)
