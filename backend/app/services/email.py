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

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Reset your Verida HQ password</title>
</head>
<body style="margin:0;padding:0;background:#f0f4f8;font-family:Inter,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4f8;padding:40px 16px;">
    <tr>
      <td align="center">
        <table cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;">
          <tr>
            <td style="background:linear-gradient(135deg,#0a1628 0%,#0d2444 60%,#0a3040 100%);padding:32px 40px;border-radius:12px 12px 0 0;text-align:center;">
              <table cellpadding="0" cellspacing="0" style="margin:0 auto;">
                <tr>
                  <td style="background:#00d4aa;border-radius:8px;width:38px;height:38px;text-align:center;vertical-align:middle;font-size:22px;font-weight:700;color:#0a1628;line-height:38px;">&#10003;</td>
                  <td style="padding-left:12px;"><span style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:-0.5px;">Verida HQ</span></td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="background:#ffffff;padding:44px 40px 36px;border-left:1px solid #e2e8f0;border-right:1px solid #e2e8f0;">
              <h1 style="margin:0 0 8px;font-size:26px;font-weight:700;color:#0a1628;line-height:1.3;">No worries &#8212;<br>let&#39;s get you back in.</h1>
              <p style="margin:18px 0 0;font-size:15px;color:#64748b;line-height:1.75;">
                We received a request to reset the password on your Verida HQ account.
                Click the button below to set a new password &#8212; this link is valid for <strong style="color:#0a1628;">1 hour</strong>.
              </p>
              <table width="100%" cellpadding="0" cellspacing="0" style="margin:36px 0 28px;">
                <tr>
                  <td align="center">
                    <a href="{reset_link}"
                       style="display:inline-block;background:#00d4aa;color:#0a1628;padding:16px 44px;border-radius:8px;text-decoration:none;font-weight:700;font-size:16px;letter-spacing:0.1px;">
                      Reset My Password
                    </a>
                  </td>
                </tr>
              </table>
              <p style="margin:0 0 4px;font-size:12px;color:#94a3b8;">Or copy and paste this URL into your browser:</p>
              <p style="margin:0;font-size:12px;color:#00d4aa;word-break:break-all;">{reset_link}</p>
            </td>
          </tr>
          <tr>
            <td style="background:#f8fafc;padding:22px 40px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 12px 12px;">
              <p style="margin:0 0 8px;font-size:13px;color:#94a3b8;line-height:1.65;">
                If you didn&#39;t request this, you can safely ignore this email &#8212; your password won&#39;t change.
                Never share this link with anyone.
              </p>
              <p style="margin:12px 0 0;font-size:12px;color:#cbd5e1;">
                <strong style="color:#0a1628;">Verida HQ</strong> &#8212; NDIS Compliance, Simplified &nbsp;&middot;&nbsp;
                <a href="https://veridahq.com" style="color:#00d4aa;text-decoration:none;">veridahq.com</a>
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                RESEND_API,
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": settings.from_email,
                    "to": [to_email],
                    "subject": "Reset your Verida HQ password",
                    "html": html,
                },
            )
            resp.raise_for_status()
            logger.info(f"Password reset email sent → {to_email}")
            return True
    except Exception as exc:
        logger.error(f"Resend error sending to {to_email}: {exc}")
        return False
