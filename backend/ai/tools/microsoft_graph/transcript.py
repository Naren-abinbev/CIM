from __future__ import annotations

from langchain_core.tools import tool

from .client import MicrosoftGraphClient


graph_client = MicrosoftGraphClient()


@tool
def get_war_room_transcript(
    team_id: str,
    channel_id: str,
) -> dict:
    """
    Retrieve the current Microsoft Teams war-room
    channel messages.

    Scheduling every 30 minutes should be handled
    by the workflow/scheduler, not inside this tool.
    """

    if not team_id:
        raise ValueError(
            "team_id is required."
        )

    if not channel_id:
        raise ValueError(
            "channel_id is required."
        )

    response = graph_client.request(
        "GET",
        (
            f"/teams/{team_id}"
            f"/channels/{channel_id}"
            "/messages"
        ),
    )

    messages = response.get(
        "value",
        [],
    )

    transcript = []

    for message in messages:

        sender = (
            message
            .get("from", {})
            .get("user", {})
            .get(
                "displayName",
                "Unknown",
            )
        )

        body = (
            message
            .get("body", {})
            .get("content", "")
        )

        created_at = message.get(
            "createdDateTime"
        )

        transcript.append(
            {
                "sender": sender,
                "created_at": created_at,
                "content": body,
            }
        )

    return {
        "success": True,
        "team_id": team_id,
        "channel_id": channel_id,
        "message_count": len(transcript),
        "messages": transcript,
    }