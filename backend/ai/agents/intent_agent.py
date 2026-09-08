from __future__ import annotations

import re
from typing import Any, Literal, TypedDict
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field, model_validator

from backend.ai.llm.llm import (
    GeminiLLMConfigurationError,
    get_gemini_llm,
)
from backend.ai.prompts.intent import (
    INTENT_SYSTEM_PROMPT,
    INTENT_USER_PROMPT,
)


IntentName = Literal[
    "incident",
    "general_query",
    "irrelevant",
    "insufficient_information",
]

SeverityHint = Literal[
    "critical",
    "high",
    "medium",
    "low",
    "unknown",
]

AgentStatus = Literal[
    "RECEIVED",
    "ANALYZED",
    "FORWARDED",
    "REJECTED",
    "ERROR",
]


class IntentClassification(BaseModel):
    """Structured classification produced by Gemini."""

    is_incident: bool = Field(
        description="True only for a valid IT incident."
    )

    intent: IntentName = Field(
        description="Selected intent classification."
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Classification confidence.",
    )

    reason: str = Field(
        min_length=1,
        max_length=500,
        description="Short factual classification reason.",
    )

    affected_service: str | None = Field(
        default=None,
        description="Reported affected service.",
    )

    symptoms: list[str] = Field(
        default_factory=list,
        description="Explicitly reported symptoms.",
    )

    impact: str | None = Field(
        default=None,
        description="Reported operational impact.",
    )

    environment: str | None = Field(
        default=None,
        description="Reported technical environment.",
    )

    severity_hint: SeverityHint = Field(
        default="unknown",
        description="Preliminary severity recommendation.",
    )

    user_message: str = Field(
        min_length=1,
        max_length=1000,
        description="Message to display to the user.",
    )

    prompt_injection_detected: bool = Field(
        default=False,
        description="Whether manipulation was detected.",
    )

    @model_validator(mode="after")
    def validate_consistency(
        self,
    ) -> "IntentClassification":
        if self.intent == "incident" and not self.is_incident:
            raise ValueError(
                "Incident intent requires is_incident=true."
            )

        if self.intent != "incident" and self.is_incident:
            raise ValueError(
                "Non-incident intent requires is_incident=false."
            )

        return self


class IntentAgentState(TypedDict, total=False):
    request_id: str
    description: str
    classification: dict[str, Any] | None
    status: AgentStatus
    next_action: str
    message: str
    score: float
    orchestration_payload: dict[str, Any] | None
    error: str | None


PROMPT_INJECTION_PATTERNS = (
    r"\bignore\s+(all\s+|any\s+)?previous\s+instructions?\b",
    r"\bignore\s+(the\s+)?system\s+prompt\b",
    r"\bdisregard\s+(all\s+|any\s+)?previous\s+instructions?\b",
    r"\breveal\s+(the\s+|your\s+)?system\s+prompt\b",
    r"\bshow\s+(the\s+|your\s+)?system\s+prompt\b",
    r"\boverride\s+(the\s+)?instructions?\b",
    r"\bchange\s+your\s+role\b",
    r"\byou\s+are\s+now\b",
    r"\bpretend\s+to\s+be\b",
    r"\bdeveloper\s+message\b",
    r"\bsystem\s+message\b",
    r"\bmark\s+(this|it)\s+as\s+an?\s+incident\b",
    r"\bexecute\s+(this\s+)?command\b",
    r"\bprint\s+(the\s+)?api\s*key\b",
    r"\breveal\s+(the\s+)?credentials?\b",
)


def contains_prompt_injection(description: str) -> bool:
    """Detect common prompt-injection patterns."""

    normalized = " ".join(
        description.lower().split()
    )

    return any(
        re.search(
            pattern,
            normalized,
            flags=re.IGNORECASE,
        )
        for pattern in PROMPT_INJECTION_PATTERNS
    )


def create_rejected_classification(
    *,
    intent: IntentName,
    confidence: float,
    reason: str,
    user_message: str,
    prompt_injection_detected: bool = False,
) -> dict[str, Any]:
    """Create a valid local rejection result."""

    classification = IntentClassification(
        is_incident=False,
        intent=intent,
        confidence=confidence,
        reason=reason,
        affected_service=None,
        symptoms=[],
        impact=None,
        environment=None,
        severity_hint="unknown",
        user_message=user_message,
        prompt_injection_detected=(
            prompt_injection_detected
        ),
    )

    return classification.model_dump()


def validate_input_node(
    state: IntentAgentState,
) -> IntentAgentState:
    """Validate the description before calling Gemini."""

    description = str(
        state.get("description", "")
    ).strip()

    request_id = (
        state.get("request_id")
        or str(uuid4())
    )

    if not description:
        message = (
            "Please provide the affected system, symptoms, "
            "environment, and operational impact."
        )

        return {
            **state,
            "request_id": request_id,
            "description": description,
            "classification": create_rejected_classification(
                intent="insufficient_information",
                confidence=1.0,
                reason="The description is empty.",
                user_message=message,
            ),
            "status": "REJECTED",
            "next_action": "RETURN_TO_USER",
            "message": message,
            "score": 1.0,
            "orchestration_payload": None,
            "error": None,
        }

    if len(description) > 5000:
        message = (
            "The description is too long. Please submit a "
            "description below 5,000 characters."
        )

        return {
            **state,
            "request_id": request_id,
            "description": description,
            "classification": create_rejected_classification(
                intent="insufficient_information",
                confidence=1.0,
                reason=(
                    "The description exceeds the supported length."
                ),
                user_message=message,
            ),
            "status": "REJECTED",
            "next_action": "RETURN_TO_USER",
            "message": message,
            "score": 1.0,
            "orchestration_payload": None,
            "error": None,
        }

    if contains_prompt_injection(description):
        message = (
            "The description contains instructions that cannot "
            "be processed as incident information. Please provide "
            "only the affected system, symptoms, and impact."
        )

        return {
            **state,
            "request_id": request_id,
            "description": description,
            "classification": create_rejected_classification(
                intent="irrelevant",
                confidence=0.99,
                reason=(
                    "The input contains an instruction-manipulation "
                    "pattern."
                ),
                user_message=message,
                prompt_injection_detected=True,
            ),
            "status": "REJECTED",
            "next_action": "RETURN_TO_USER",
            "message": message,
            "score": 0.99,
            "orchestration_payload": None,
            "error": None,
        }

    return {
        **state,
        "request_id": request_id,
        "description": description,
        "classification": None,
        "status": "RECEIVED",
        "next_action": "ANALYZE_INTENT",
        "message": "Description accepted for analysis.",
        "score": 0.0,
        "orchestration_payload": None,
        "error": None,
    }


def route_after_validation(
    state: IntentAgentState,
) -> Literal["classify", "complete"]:
    if state.get("status") == "RECEIVED":
        return "classify"

    return "complete"


def classify_intent_node(
    state: IntentAgentState,
) -> IntentAgentState:
    """Classify the description using Gemini."""

    try:
        llm = get_gemini_llm()

        structured_llm = llm.with_structured_output(
            IntentClassification
        )

        response = structured_llm.invoke(
            [
                SystemMessage(
                    content=INTENT_SYSTEM_PROMPT
                ),
                HumanMessage(
                    content=INTENT_USER_PROMPT.format(
                        description=state["description"],
                    )
                ),
            ]
        )

        if isinstance(response, IntentClassification):
            classification = response
        else:
            classification = IntentClassification.model_validate(
                response
            )

        return {
            **state,
            "classification": classification.model_dump(),
            "status": "ANALYZED",
            "next_action": "ROUTE_RESULT",
            "message": classification.user_message,
            "score": classification.confidence,
            "orchestration_payload": None,
            "error": None,
        }

    except GeminiLLMConfigurationError as exc:
        return {
            **state,
            "classification": None,
            "status": "ERROR",
            "next_action": "CHECK_GEMINI_CONFIGURATION",
            "message": (
                "The Gemini intent agent is not configured."
            ),
            "score": 0.0,
            "orchestration_payload": None,
            "error": f"{type(exc).__name__}: {exc}",
        }

    except Exception as exc:
        return {
            **state,
            "classification": None,
            "status": "ERROR",
            "next_action": "RETRY_OR_CONTACT_SUPPORT",
            "message": (
                "The intent agent could not complete "
                "the classification."
            ),
            "score": 0.0,
            "orchestration_payload": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def route_classification(
    state: IntentAgentState,
) -> Literal["forward", "reject", "complete"]:
    if state.get("status") == "ERROR":
        return "complete"

    classification = state.get("classification") or {}

    if (
        classification.get("is_incident") is True
        and classification.get("intent") == "incident"
    ):
        return "forward"

    return "reject"


def forward_to_orchestration_node(
    state: IntentAgentState,
) -> IntentAgentState:
    """Prepare a valid incident for orchestration."""

    classification = state.get("classification") or {}

    payload = {
        "request_id": state["request_id"],
        "event_type": "INCIDENT_INTENT_ACCEPTED",
        "source": "intent_agent",
        "target": "agent_orchestrator",
        "next_agent": "validation_agent",
        "incident": {
            "description": state["description"],
            "affected_service": classification.get(
                "affected_service"
            ),
            "symptoms": classification.get("symptoms", []),
            "impact": classification.get("impact"),
            "environment": classification.get("environment"),
            "severity_hint": classification.get(
                "severity_hint",
                "unknown",
            ),
        },
        "intent_analysis": {
            "is_incident": classification.get("is_incident"),
            "intent": classification.get("intent"),
            "confidence": classification.get("confidence"),
            "reason": classification.get("reason"),
            "prompt_injection_detected": classification.get(
                "prompt_injection_detected",
                False,
            ),
        },
    }

    return {
        **state,
        "status": "FORWARDED",
        "next_action": "SEND_TO_ORCHESTRATION",
        "message": (
            "The description was identified as a valid incident "
            "and forwarded to orchestration."
        ),
        "score": float(
            classification.get("confidence", 0.0)
        ),
        "orchestration_payload": payload,
        "error": None,
    }


def reject_to_user_node(
    state: IntentAgentState,
) -> IntentAgentState:
    """Return a non-incident result to the user."""

    classification = state.get("classification") or {}

    message = classification.get(
        "user_message",
        "The description does not represent a valid IT incident.",
    )

    return {
        **state,
        "status": "REJECTED",
        "next_action": "RETURN_TO_USER",
        "message": message,
        "score": float(
            classification.get("confidence", 0.0)
        ),
        "orchestration_payload": None,
        "error": None,
    }


def complete_node(
    state: IntentAgentState,
) -> IntentAgentState:
    return state


def build_intent_graph():
    """Build and compile the LangGraph workflow."""

    builder = StateGraph(IntentAgentState)

    builder.add_node(
        "validate_input",
        validate_input_node,
    )
    builder.add_node(
        "classify",
        classify_intent_node,
    )
    builder.add_node(
        "forward",
        forward_to_orchestration_node,
    )
    builder.add_node(
        "reject",
        reject_to_user_node,
    )
    builder.add_node(
        "complete",
        complete_node,
    )

    builder.add_edge(
        START,
        "validate_input",
    )

    builder.add_conditional_edges(
        "validate_input",
        route_after_validation,
        {
            "classify": "classify",
            "complete": "complete",
        },
    )

    builder.add_conditional_edges(
        "classify",
        route_classification,
        {
            "forward": "forward",
            "reject": "reject",
            "complete": "complete",
        },
    )

    builder.add_edge("forward", END)
    builder.add_edge("reject", END)
    builder.add_edge("complete", END)

    return builder.compile()


intent_graph = build_intent_graph()


def analyze_intent(
    description: str,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Run the intent-analysis workflow."""

    initial_state: IntentAgentState = {
        "request_id": request_id or str(uuid4()),
        "description": description,
        "classification": None,
        "status": "RECEIVED",
        "next_action": "VALIDATE_INPUT",
        "message": "",
        "score": 0.0,
        "orchestration_payload": None,
        "error": None,
    }

    result = intent_graph.invoke(initial_state)

    return {
        "request_id": result.get("request_id"),
        "status": result.get("status"),
        "next_action": result.get("next_action"),
        "message": result.get("message"),
        "score": result.get("score"),
        "classification": result.get("classification"),
        "orchestration_payload": result.get(
            "orchestration_payload"
        ),
        "error": result.get("error"),
    }