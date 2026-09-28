"""Best-effort email notifications (MailHog in dev; any plain SMTP relay in
prod). Nothing here may ever fail the request that triggers it — callers
invoke this after `db.commit()`, and every failure is caught and logged.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str) -> None:
    message = EmailMessage()
    message["From"] = settings.smtp_from_address
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(
            settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds
        ) as client:
            client.send_message(message)
    except OSError:
        # Unreachable/misconfigured SMTP relay must never fail the caller's
        # request — log and move on. OSError covers socket/connection/timeout
        # errors; smtplib's own exceptions (SMTPException) are also OSError
        # subclasses in modern Python, so this catches those too.
        logger.warning("Failed to send email to %s (subject=%r)", to, subject, exc_info=True)


_STATUS_MESSAGES: dict[str, str] = {
    "submitted": "Your application has been submitted and is awaiting review.",
    "changes_requested": "A reviewer has requested changes to your application.",
    "approved": "Your application has been approved.",
    "rejected": "Your application has been rejected.",
}


def notify_status_change(
    *, owner_label: str, recipient_email: str, to_status: str, note: str | None = None
) -> None:
    """`owner_label` is a short human description, e.g. "Hospital application
    for Springfield General" or "HCP profile for Dr. Jane Doe"."""
    headline = _STATUS_MESSAGES.get(to_status, f"Status changed to {to_status}.")
    body = f"{owner_label}\n\n{headline}"
    if note:
        body += f"\n\nReviewer note:\n{note}"
    send_email(recipient_email, f"medita-ai: {owner_label} — {to_status}", body)
