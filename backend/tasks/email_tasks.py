import logging

from backend.core.celery_app import celery_app
from backend.services.email_service import (
    send_invite_email,
    send_verification_email,
    send_welcome_email,
)

logger = logging.getLogger(__name__)


@celery_app.task(name="send_invite_email_task", bind=True, max_retries=3, default_retry_delay=30)
def send_invite_email_task(self, to_email: str, invite_token: str, inviter_name: str, org_name: str, role: str):
    """Runs on a Celery worker, not in the request/response cycle - so a slow
    or momentarily-down email provider never makes POST /invites hang. The
    retry (3 attempts, 30s apart) covers transient failures (provider hiccup,
    network blip); a permanent failure (bad API key, invalid recipient) just
    exhausts its retries and shows up in the worker logs / Celery result
    backend rather than crashing anything user-facing.
    """
    logger.info("send_invite_email_task started (to_email=%s, attempt=%s)", to_email, self.request.retries + 1)
    try:
        send_invite_email(
            to_email=to_email,
            invite_token=invite_token,
            inviter_name=inviter_name,
            org_name=org_name,
            role=role,
        )
    except Exception as exc:
        logger.warning(
            "send_invite_email_task failed, retrying (to_email=%s, attempt=%s): %s",
            to_email, self.request.retries + 1, exc,
        )
        raise self.retry(exc=exc)


@celery_app.task(name="send_welcome_email_task", bind=True, max_retries=3, default_retry_delay=30)
def send_welcome_email_task(self, to_email: str, full_name: str, org_name: str):
    logger.info("send_welcome_email_task started (to_email=%s, attempt=%s)", to_email, self.request.retries + 1)
    try:
        send_welcome_email(to_email=to_email, full_name=full_name, org_name=org_name)
    except Exception as exc:
        logger.warning(
            "send_welcome_email_task failed, retrying (to_email=%s, attempt=%s): %s",
            to_email, self.request.retries + 1, exc,
        )
        raise self.retry(exc=exc)


@celery_app.task(name="send_verification_email_task", bind=True, max_retries=3, default_retry_delay=30)
def send_verification_email_task(
    self, to_email: str, full_name: str, org_name: str, verification_token: str
):
    logger.info("send_verification_email_task started (to_email=%s, attempt=%s)", to_email, self.request.retries + 1)
    try:
        send_verification_email(
            to_email=to_email,
            full_name=full_name,
            org_name=org_name,
            verification_token=verification_token,
        )
    except Exception as exc:
        logger.warning(
            "send_verification_email_task failed, retrying (to_email=%s, attempt=%s): %s",
            to_email, self.request.retries + 1, exc,
        )
        raise self.retry(exc=exc)
