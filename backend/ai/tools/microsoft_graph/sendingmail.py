from __future__ import annotations

import os

from langchain_core.tools import tool

from .client import MicrosoftGraphClient


graph_client = MicrosoftGraphClient()


@tool
def send_stakeholder_email(
    recipients: list[str],
    subject: str,
    body: str,
) -> dict:
    """
    Send an incident-related email to stakeholders
    using Microsoft Graph.
    """

    if not recipients:
        raise ValueError(
            "At least one recipient is required."
        )

    if not subject:
        raise ValueError(
            "Email subject is required."
        )

    if not body:
        raise ValueError(
            "Email body is required."
        )

    mailbox = os.environ.get(
        "GRAPH_MAILBOX_USER"
    )

    if not mailbox:
        raise RuntimeError(
            "GRAPH_MAILBOX_USER is not configured."
        )

    to_recipients = [
        {
            "emailAddress": {
                "address": email
            }
        }
        for email in recipients
    ]

    payload = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": body,
            },
            "toRecipients": to_recipients,
        },
        "saveToSentItems": True,
    }

    graph_client.request(
        "POST",
        f"/users/{mailbox}/sendMail",
        json=payload,
    )

    return {
        "success": True,
        "recipients": recipients,
        "subject": subject,
    }