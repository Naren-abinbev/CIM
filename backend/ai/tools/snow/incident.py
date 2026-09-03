from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from .client import ServiceNowClient


servicenow_client = ServiceNowClient()


@tool
def create_incident(
    requester_email: str,
    caller_id: str,
    short_description: str,
    description: str,
    priority: str,
    severity: str,
    resolution_steps: str,
    close_notes: str,
    assignment_group: str,
) -> dict[str, Any]:
    """
    Create an incident ticket in ServiceNow.

    Required information:
    - requester_email: Email address of the person who requested/reported
      the incident.
    - caller_id: ServiceNow caller/sys_id or caller identifier.
    - short_description: Short summary of the incident.
    - description: Detailed incident description.
    - priority: Incident priority.
    - severity: Incident severity.
    - resolution_steps: Steps taken or recommended to resolve the incident.
    - close_notes: Notes describing the final resolution/closure.
    - assignment_group: ServiceNow assignment group.

    Returns the created ServiceNow incident number and metadata.
    """

    # ---------------------------------------------------------
    # Validate required input
    # ---------------------------------------------------------

    required_fields = {
        "requester_email": requester_email,
        "caller_id": caller_id,
        "short_description": short_description,
        "description": description,
        "priority": priority,
        "severity": severity,
        "resolution_steps": resolution_steps,
        "close_notes": close_notes,
        "assignment_group": assignment_group,
    }

    missing_fields = [
        field
        for field, value in required_fields.items()
        if not value or not str(value).strip()
    ]

    if missing_fields:
        raise ValueError(
            "Missing required ServiceNow fields: "
            + ", ".join(missing_fields)
        )

    # ---------------------------------------------------------
    # Build ServiceNow incident payload
    # ---------------------------------------------------------

    incident_payload = {
        "caller_id": caller_id,
        "short_description": short_description,
        "description": description,
        "priority": priority,
        "severity": severity,
        "assignment_group": assignment_group,

        # Keep requester information available in the
        # incident record/work notes if your ServiceNow
        # instance does not have a dedicated requester field.
        "work_notes": (
            f"Requester Email: {requester_email}\n\n"
            f"Resolution Steps:\n"
            f"{resolution_steps}"
        ),

        "close_notes": close_notes,
    }

    # ---------------------------------------------------------
    # Create ServiceNow incident
    # ---------------------------------------------------------

    response = servicenow_client.request(
        method="POST",
        endpoint="/incident",
        json=incident_payload,
    )

    result = response.get("result", {})

    incident_number = result.get("number")
    sys_id = result.get("sys_id")

    if not incident_number:
        raise RuntimeError(
            "ServiceNow incident creation succeeded but "
            "no incident number was returned."
        )

    return {
        "success": True,
        "incident_number": incident_number,
        "sys_id": sys_id,
        "requester_email": requester_email,
        "caller_id": caller_id,
        "short_description": result.get(
            "short_description",
            short_description,
        ),
        "priority": result.get(
            "priority",
            priority,
        ),
        "severity": result.get(
            "severity",
            severity,
        ),
        "assignment_group": result.get(
            "assignment_group",
            assignment_group,
        ),
        "message": (
            f"ServiceNow incident "
            f"{incident_number} created successfully."
        ),
    }