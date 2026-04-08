"""Transactional email via Resend."""

import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

RESEND_API = "https://api.resend.com/emails"


async def send_password_reset_email(to_email: str, reset_link: str) -> bool:
    """Send a Verida-branded password reset email via Resend."""
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not configured — cannot send branded email")
        return False

    html = f"""
    <div style="font-family:Inter,Arial,sans-serif;max-width:560px;margin:0 auto;background:#f8fafc;padding:32px 16px;">
      <div style="background:linear-gradient(135deg,#1B365D,#2A9D8F);padding:28px 32px;border-radius:12px 12px 0 0;text-align:center;">
        <span style="color:white;font-size:22px;font-weight:700;letter-spacing:-0.5px;">✓ Verida</span>
      </div>
      <div style="background:#ffffff;padding:40px 32px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 12px 12px;">
        <h2 style="color:#1B365D;margin-top:0;font-size:22px;">Reset your password</h2>
        <p style="color:#64748b;line-height:1.7;margin-bottom:28px;">
          We received a request to reset the password on your Verida account.
          Click the button below — the link is valid for <strong>1 hour</strong>.
        </p>
        <div style="text-align:center;margin:32px 0;">
          <a href="{reset_link}"
             style="background:#2A9D8F;color:#ffffff;padding:14px 32px;border-radius:8px;
                    text-decoration:none;font-weight:600;font-size:16px;display:inline-block;">
            Reset Password
          </a>
        </div>
        <p style="color:#94a3b8;font-size:13px;line-height:1.6;border-top:1px solid #f1f5f9;padding-top:20px;margin-bottom:0;">
          If you didn't request this, you can safely ignore this email —
          your password won't change. Do not share this link with anyone.
        </p>
      </div>
      <p style="text-align:center;color:#cbd5e1;font-size:12px;margin-top:20px;">
        © 2025 Verida · veridahq.com
      </p>
    </div>
    """

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                RESEND_API,
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": settings.from_email,
                    "to": [to_email],
                    "subject": "Reset your Verida password",
                    "html": html,
                },
            )
            resp.raise_for_status()
            logger.info(f"Password reset email sent → {to_email}")
            return True
    except Exception as exc:
        logger.error(f"Resend error sending to {to_email}: {exc}")
        return False
