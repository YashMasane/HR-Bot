"""Provider-specific email sending. Only this file knows about SendGrid's API
shape - everything else in the app calls send_invite_email() and doesn't care
who's actually delivering the message. Swapping providers later means
rewriting this one function, not touching routes/tasks.

Uses SendGrid's Single Sender Verification (EMAIL_FROM_ADDRESS is a
verified individual address, not an authenticated domain) - fine for
sending to arbitrary recipients, unlike Resend's shared sandbox domain
which restricted delivery to the account owner's own email only.
"""

import logging

import httpx

from backend.core.config import settings

logger = logging.getLogger(__name__)

SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"


def _send(to_email: str, subject: str, html: str) -> None:
    if not settings.SENDGRID_API_KEY:
        logger.error("Cannot send email to %s: SENDGRID_API_KEY is not configured.", to_email)
        raise RuntimeError("SENDGRID_API_KEY is not configured - cannot send email.")

    try:
        response = httpx.post(
            SENDGRID_API_URL,
            headers={
                "Authorization": f"Bearer {settings.SENDGRID_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "personalizations": [{"to": [{"email": to_email}]}],
                "from": {"email": settings.EMAIL_FROM_ADDRESS, "name": settings.EMAIL_FROM_NAME},
                "subject": subject,
                "content": [{"type": "text/html", "value": html}],
            },
            timeout=10.0,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        logger.exception("Failed to send email to %s (subject=%r)", to_email, subject)
        raise

    logger.info("Email sent to %s (subject=%r)", to_email, subject)


def send_invite_email(
    to_email: str, invite_token: str, inviter_name: str, org_name: str, role: str
) -> None:
    accept_url = f"{settings.FRONTEND_BASE_URL}/accept-invite?token={invite_token}"
    html = f"""
    <p>Hi,</p>
    <p><strong>{inviter_name}</strong> has invited you to join
    <strong>{org_name}</strong> on HR Bot as a <strong>{role}</strong>.</p>
    <p><a href="{accept_url}">Accept your invite</a></p>
    <p>This link expires in {settings.INVITE_EXPIRE_HOURS // 24} days. If you weren't
    expecting this invite, you can ignore this email.</p>
    """
    _send(to_email, f"You're invited to join {org_name}", html)


def send_verification_email(
    to_email: str, full_name: str, org_name: str, verification_token: str
) -> None:
    """Sent immediately on setup-organization, before anything is actually
    created. The org + SUPER_ADMIN account only come into existence once the
    recipient clicks this link and it hits POST /auth/verify-email - see
    OrganizationSignupRequest.
    """
    verify_url = f"{settings.FRONTEND_BASE_URL}/verify-email?token={verification_token}"
    html = f"""
    <p>Hi {full_name},</p>
    <p>You're almost done setting up <strong>{org_name}</strong> on HR Bot.
    Confirm this email address to finish creating your organization:</p>
    <p><a href="{verify_url}">Verify your email</a></p>
    <p>This link expires in {settings.SIGNUP_VERIFICATION_EXPIRE_HOURS} hours. If you
    didn't request this, you can ignore this email.</p>
    """
    _send(to_email, f"Verify your email to finish setting up {org_name}", html)


def send_welcome_email(to_email: str, full_name: str, org_name: str) -> None:
    """Sent once, right after POST /auth/verify-email creates the org and its
    first SUPER_ADMIN. By this point the email is already confirmed
    deliverable (that's what verify-email just proved), so this is a pure
    "you're all set" notice rather than doing any verification itself.
    """
    html = f"""
    <p>Hi {full_name},</p>
    <p>Welcome to HR Bot! <strong>{org_name}</strong> is now set up, and you're
    signed in as the super admin.</p>
    <p>From here you can invite department admins and employees, and start
    configuring your organization's policies.</p>
    """
    _send(to_email, "Welcome to HR Bot", html)
