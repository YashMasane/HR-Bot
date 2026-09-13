"""Provider-specific email sending. Only this file knows about Resend's API
shape - everything else in the app calls send_invite_email() and doesn't care
who's actually delivering the message. Swapping providers later (SES,
SendGrid, ...) means rewriting this one function, not touching routes/tasks.
"""

import httpx

from backend.core.config import settings

RESEND_API_URL = "https://api.resend.com/emails"


def send_invite_email(
    to_email: str, invite_token: str, inviter_name: str, org_name: str, role: str
) -> None:
    if not settings.RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY is not configured - cannot send invite email.")

    accept_url = f"{settings.FRONTEND_BASE_URL}/accept-invite?token={invite_token}"
    html = f"""
    <p>Hi,</p>
    <p><strong>{inviter_name}</strong> has invited you to join
    <strong>{org_name}</strong> on HR Bot as a <strong>{role}</strong>.</p>
    <p><a href="{accept_url}">Accept your invite</a></p>
    <p>This link expires in {settings.INVITE_EXPIRE_HOURS // 24} days. If you weren't
    expecting this invite, you can ignore this email.</p>
    """

    response = httpx.post(
        RESEND_API_URL,
        headers={
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "from": f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>",
            "to": [to_email],
            "subject": f"You're invited to join {org_name}",
            "html": html,
        },
        timeout=10.0,
    )
    response.raise_for_status()
