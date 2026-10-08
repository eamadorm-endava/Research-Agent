"""Resolve a live Agent Engine without retaining a failed startup lookup."""

from functools import lru_cache

import vertexai
from fastapi import HTTPException
from vertexai import agent_engines

from .config import UI_CONFIG


@lru_cache(maxsize=1)
def get_remote_agent():
    """Resolve an explicit resource or exactly one agent with the configured name."""
    try:
        vertexai.init(project=UI_CONFIG.PROJECT_ID, location=UI_CONFIG.REGION)
        if UI_CONFIG.AGENT_RESOURCE_NAME:
            return agent_engines.get(UI_CONFIG.AGENT_RESOURCE_NAME)
        agents = [
            agent
            for agent in agent_engines.list()
            if agent.api_resource.display_name == UI_CONFIG.AGENT_DISPLAY_NAME
        ]
        if len(agents) != 1:
            raise ValueError("Expected exactly one matching Agent Engine")
        return agents[0]
    except Exception:  # noqa: BLE001 - API/UI boundary must not disclose credentials
        # lru_cache stores successes only; a later request can recover.
        raise HTTPException(503, "Agent Engine is unavailable or ambiguous") from None
