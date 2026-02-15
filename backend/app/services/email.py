"""Optional email sending service using aiosmtplib."""

import logging

from ..core.config import settings

_log = logging.getLogger(__name__)


def is_email_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_from)


async def send_email(to: str, subject: str, html_body: str) -> bool:
    """Send an email. Returns True on success, False if SMTP not configured or error."""
    if not is_email_configured():
        _log.warning("SMTP not configured, email not sent to %s", to)
        return False

    try:
        import aiosmtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from
        msg["To"] = to
        msg.attach(MIMEText(html_body, "html"))

        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            use_tls=settings.smtp_tls,
        )
        return True
    except ImportError:
        _log.warning("aiosmtplib not installed, email not sent")
        return False
    except Exception as e:
        _log.error("Email send failed: %s", e)
        return False


async def send_password_reset(to: str, token: str) -> bool:
    reset_url = f"{settings.frontend_url}/reset-password?token={token}"
    html = f"""\
<h2>Password Reset — PredomicsApp</h2>
<p>Click the link below to reset your password. This link expires in 1 hour.</p>
<p><a href="{reset_url}">{reset_url}</a></p>
<p>If you did not request this, you can safely ignore this email.</p>
"""
    return await send_email(to, "PredomicsApp Password Reset", html)
