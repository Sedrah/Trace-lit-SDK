"""
Email sender for verification links.

If TRACELIT_SMTP_HOST is configured, sends a real email via SMTP.
Otherwise logs the link to stdout so admins can relay it manually
(useful for air-gapped deployments with no outbound email).
"""
from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage

logger = logging.getLogger("trace_lit.api")


def send_verification_email(to_email: str, verify_url: str) -> None:
    """Send (or log) a verification link. Never raises — failures are logged only."""
    smtp_host = os.getenv("TRACELIT_SMTP_HOST", "")
    if not smtp_host:
        # Air-gapped / dev fallback — log so admin can send manually
        logger.info(
            "EMAIL NOT CONFIGURED — verification link for %s:\n  %s",
            to_email,
            verify_url,
        )
        print(f"\n[Trace-lit] Verification link for {to_email}:\n  {verify_url}\n")
        return

    smtp_port = int(os.getenv("TRACELIT_SMTP_PORT", "587"))
    smtp_user = os.getenv("TRACELIT_SMTP_USER", "")
    smtp_pass = os.getenv("TRACELIT_SMTP_PASS", "")
    from_addr = os.getenv("TRACELIT_SMTP_FROM", smtp_user or "noreply@trace-lit.com")

    msg = EmailMessage()
    msg["Subject"] = "Verify your Trace-lit account"
    msg["From"]    = from_addr
    msg["To"]      = to_email
    msg.set_content(
        f"Hi,\n\n"
        f"Click the link below to verify your email and get your Trace-lit API key:\n\n"
        f"  {verify_url}\n\n"
        f"This link expires in 24 hours.\n\n"
        f"If you didn't request this, you can ignore this email.\n\n"
        f"— Trace-lit"
    )

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls(context=ctx)
            if smtp_user:
                server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        logger.info("Verification email sent to %s", to_email)
    except Exception as exc:
        logger.error("Failed to send verification email to %s: %s", to_email, exc)
        # Still log the link so the user isn't blocked
        print(f"\n[Trace-lit] Email failed — verification link for {to_email}:\n  {verify_url}\n")
