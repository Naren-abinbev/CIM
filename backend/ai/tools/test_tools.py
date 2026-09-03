from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any


# ============================================================
# Logging
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(name)s | "
        "%(message)s"
    ),
)

logger = logging.getLogger("tool-test")


# ============================================================
# Import tools
# ============================================================

from tools.rag.rag_tools import rag_search

from tools.microsoft_graph.war_room import (
    create_war_room,
)

from tools.microsoft_graph.transcript import (
    get_war_room_transcript,
)

from tools.microsoft_graph.sendingmail import (
    send_stakeholder_email,
)

from tools.snow.incident import (
    create_incident,
)


# ============================================================
# Helpers
# ============================================================

def print_result(
    tool_name: str,
    result: Any,
) -> None:

    print("\n" + "=" * 80)
    print(f"RESULT: {tool_name}")
    print("=" * 80)

    if isinstance(result, dict):

        print(
            json.dumps(
                result,
                indent=2,
                default=str,
            )
        )

    else:
        print(result)


def run_test(
    tool_name: str,
    function,
    arguments: dict[str, Any],
) -> bool:

    print("\n" + "#" * 80)
    print(f"TESTING: {tool_name}")
    print("#" * 80)

    try:

        result = function.invoke(arguments)

        print_result(
            tool_name,
            result,
        )

        print(
            f"\n✅ {tool_name} PASSED"
        )

        return True

    except Exception as exc:

        logger.exception(
            "%s failed",
            tool_name,
        )

        print(
            f"\n❌ {tool_name} FAILED"
        )

        print(
            f"Error: {exc}"
        )

        return False


# ============================================================
# Environment validation
# ============================================================

def check_environment() -> None:

    print("\n" + "=" * 80)
    print("ENVIRONMENT CONFIGURATION")
    print("=" * 80)

    variables = {
        # RAG
        "AZURE_OPENAI_ENDPOINT":
            "Azure OpenAI",
        "AZURE_OPENAI_API_KEY":
            "Azure OpenAI",
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT":
            "Azure OpenAI Embedding",

        # Graph
        "GRAPH_TENANT_ID":
            "Microsoft Graph",
        "GRAPH_CLIENT_ID":
            "Microsoft Graph",
        "GRAPH_CLIENT_SECRET":
            "Microsoft Graph",
        "GRAPH_MAILBOX_USER":
            "Microsoft Graph Mail",

        # ServiceNow
        "SERVICENOW_INSTANCE_URL":
            "ServiceNow",
        "SERVICENOW_CLIENT_ID":
            "ServiceNow OAuth",
        "SERVICENOW_CLIENT_SECRET":
            "ServiceNow OAuth",
    }

    for variable, service in variables.items():

        configured = bool(
            os.getenv(variable)
        )

        status = (
            "✅ configured"
            if configured
            else "❌ missing"
        )

        print(
            f"{variable:<45} "
            f"{status:<15} "
            f"({service})"
        )

    print(
        "\nChromaDB directory: "
        f"{os.getenv('CHROMA_PERSIST_DIRECTORY', './data/chroma')}"
    )

    print(
        "ChromaDB collection: "
        f"{os.getenv('CHROMA_COLLECTION_NAME', 'incidents')}"
    )


# ============================================================
# 1. RAG TEST
# ============================================================

def test_rag() -> bool:

    return run_test(
        "RAG Search",
        rag_search,
        {
            "query": (
                "Application is returning HTTP 503 "
                "errors after deployment"
            ),
            "top_k": 5,
        },
    )


# ============================================================
# 2. GRAPH WAR ROOM TEST
# ============================================================

def test_war_room() -> bool:

    stakeholder_emails = os.getenv(
        "TEST_STAKEHOLDER_EMAILS",
        "",
    )

    if not stakeholder_emails:

        print(
            "\n⚠️ TEST_STAKEHOLDER_EMAILS is not configured."
        )

        print(
            "Skipping create_war_room test."
        )

        return False

    stakeholders = [
        email.strip()
        for email in stakeholder_emails.split(",")
        if email.strip()
    ]

    return run_test(
        "Create War Room",
        create_war_room,
        {
            "incident_number":
                "TEST-INC-001",

            "incident_summary":
                "Integration test - "
                "do not treat as production incident",

            "stakeholder_emails":
                stakeholders,
        },
    )


# ============================================================
# 3. TRANSCRIPT TEST
# ============================================================

def test_transcript() -> bool:

    team_id = os.getenv(
        "TEST_GRAPH_TEAM_ID"
    )

    channel_id = os.getenv(
        "TEST_GRAPH_CHANNEL_ID"
    )

    if not team_id or not channel_id:

        print(
            "\n⚠️ TEST_GRAPH_TEAM_ID or "
            "TEST_GRAPH_CHANNEL_ID is missing."
        )

        print(
            "Skipping transcript test."
        )

        return False

    return run_test(
        "Get War Room Transcript",
        get_war_room_transcript,
        {
            "team_id": team_id,
            "channel_id": channel_id,
        },
    )


# ============================================================
# 4. EMAIL TEST
# ============================================================

def test_email() -> bool:

    recipients = os.getenv(
        "TEST_EMAIL_RECIPIENTS",
        "",
    )

    if not recipients:

        print(
            "\n⚠️ TEST_EMAIL_RECIPIENTS is not configured."
        )

        print(
            "Skipping email test."
        )

        return False

    recipient_list = [
        email.strip()
        for email in recipients.split(",")
        if email.strip()
    ]

    return run_test(
        "Send Stakeholder Email",
        send_stakeholder_email,
        {
            "recipients":
                recipient_list,

            "subject":
                "[TEST] Incident Management "
                "Tool Integration Test",

            "body":
                """
                <html>
                    <body>
                        <h3>Tool Integration Test</h3>

                        <p>
                            This is a test email generated
                            by the incident-management
                            integration test.
                        </p>

                        <p>
                            No production incident
                            was created by this test.
                        </p>
                    </body>
                </html>
                """,
        },
    )


# ============================================================
# 5. SERVICENOW TEST
# ============================================================

def test_servicenow() -> bool:

    caller_id = os.getenv(
        "TEST_SERVICENOW_CALLER_ID"
    )

    assignment_group = os.getenv(
        "TEST_SERVICENOW_ASSIGNMENT_GROUP"
    )

    if not caller_id:

        print(
            "\n⚠️ TEST_SERVICENOW_CALLER_ID "
            "is not configured."
        )

        print(
            "Skipping ServiceNow test."
        )

        return False

    if not assignment_group:

        print(
            "\n⚠️ TEST_SERVICENOW_ASSIGNMENT_GROUP "
            "is not configured."
        )

        print(
            "Skipping ServiceNow test."
        )

        return False

    return run_test(
        "Create ServiceNow Incident",
        create_incident,
        {
            "requester_email":
                "test.user@company.com",

            "caller_id":
                caller_id,

            "short_description":
                "[TEST] Incident Management "
                "Tool Integration Test",

            "description":
                (
                    "This is an integration test "
                    "for the ServiceNow custom tool. "
                    "This ticket can be closed after "
                    "validation."
                ),

            "priority":
                "4",

            "severity":
                "4",

            "resolution_steps":
                (
                    "Integration test completed. "
                    "No production troubleshooting "
                    "was performed."
                ),

            "close_notes":
                (
                    "Test incident created successfully "
                    "by the ServiceNow integration test."
                ),

            "assignment_group":
                assignment_group,
        },
    )


# ============================================================
# Main
# ============================================================

def main() -> None:

    check_environment()

    results = {}

    # RAG
    results["RAG Search"] = test_rag()

    # Microsoft Graph
    results["Create War Room"] = test_war_room()
    results["Get Transcript"] = test_transcript()
    results["Send Email"] = test_email()

    # ServiceNow
    results["Create Incident"] = test_servicenow()

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print("\n\n")
    print("=" * 80)
    print("TOOL TEST SUMMARY")
    print("=" * 80)

    passed = 0
    failed = 0

    for name, success in results.items():

        if success:

            print(
                f"✅ {name}"
            )

            passed += 1

        else:

            print(
                f"❌ {name}"
            )

            failed += 1

    print("\n" + "-" * 80)

    print(
        f"Passed: {passed}"
    )

    print(
        f"Failed/Skipped: {failed}"
    )

    print("=" * 80)

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()