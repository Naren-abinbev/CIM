from __future__ import annotations

import os

from langchain_core.tools import tool

from .client import MicrosoftGraphClient


graph_client = MicrosoftGraphClient()


@tool
def create_war_room(
    incident_number: str,
    incident_summary: str,
    stakeholder_emails: list[str],
) -> dict:
    """
    Create a Microsoft Teams war room for an incident
    and add the required stakeholders.

    The tool handles Microsoft Graph authentication internally.
    """

    if not incident_number:
        raise ValueError(
            "incident_number is required."
        )

    if not stakeholder_emails:
        raise ValueError(
            "At least one stakeholder is required."
        )

    team_name = (
        f"Incident War Room - "
        f"{incident_number}"
    )

    payload = {
        "template@odata.bind": (
            "https://graph.microsoft.com/v1.0/"
            "$metadata#teamsTemplates/"
            "('standard')"
        ),
        "displayName": team_name,
        "description": incident_summary,
        "visibility": "private",
    }

    team = graph_client.request(
        "POST",
        "/teams",
        json=payload,
    )

    team_id = team.get("id")

    if not team_id:
        raise RuntimeError(
            "Microsoft Graph did not return "
            "the created team ID."
        )

    for email in stakeholder_emails:

        user = graph_client.request(
            "GET",
            f"/users/{email}",
        )

        user_id = user.get("id")

        if not user_id:
            raise RuntimeError(
                f"Unable to find Graph user: {email}"
            )

        member_payload = {
            "@odata.type": (
                "#microsoft.graph.aadUserConversationMember"
            ),
            "roles": ["member"],
            "user@odata.bind": (
                "https://graph.microsoft.com/v1.0/"
                f"users('{user_id}')"
            ),
        }

        graph_client.request(
            "POST",
            f"/teams/{team_id}/members",
            json=member_payload,
        )

    return {
        "success": True,
        "incident_number": incident_number,
        "team_id": team_id,
        "stakeholders_added": len(
            stakeholder_emails
        ),
    }