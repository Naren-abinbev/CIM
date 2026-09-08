"""Stable identifiers for agents used by the application.

Keep these IDs stable after they have been used in the database. Agent names
can change for display purposes without changing historical execution logs.
"""

from __future__ import annotations

from backend.core.config import get_settings

AGENT_CONFIG_KEYS: dict[str, str] = {
    "sample-investigation-agent": "agent_id_sample_investigation_agent",
}


def _environment_key(agent_name: str) -> str:
    return "AGENT_ID_" + agent_name.upper().replace("-", "_")



def get_agent_id(agent_name: str) -> str:
    """Return the stable ID configured for an agent name."""
    config_key = AGENT_CONFIG_KEYS.get(agent_name)
    if config_key is None:
        raise ValueError(f"Unknown agent name: {agent_name}")

    value = str(getattr(get_settings(), config_key)).strip()
    if not value:
        raise ValueError(
            f"Missing {_environment_key(agent_name)} environment variable"
        )
    return value


def get_agent_name(agent_id: str) -> str:
    """Return the configured agent name for a stable agent ID."""
    settings = get_settings()
    for agent_name, config_key in AGENT_CONFIG_KEYS.items():
        if str(getattr(settings, config_key)).strip() == agent_id:
            return agent_name
    raise ValueError(f"Unknown agent ID: {agent_id}")
