"""Builder for the public agent invitation payload."""

from copy import deepcopy
from typing import Any

from app.services.agent_invitation_core import (
    INVITATION_CORE_FIELDS,
    INVITATION_INTRO_FIELDS,
)
from app.services.agent_invitation_lineage import INVITATION_LINEAGE_FIELDS
from app.services.agent_invitation_surfaces import INVITATION_SURFACE_FIELDS
from app.services.agent_start_packet import get_agent_start_packet


def build_agent_invitation(generated_at: str) -> dict[str, Any]:
    """Return a fresh invitation payload with dynamic fields inserted."""
    return {
        "id": "agent-resonance-onboarding",
        "version": "2026-06-18",
        "generated_at": generated_at,
        **deepcopy(INVITATION_INTRO_FIELDS),
        "agent_start_packet": get_agent_start_packet(),
        **deepcopy(INVITATION_CORE_FIELDS),
        **deepcopy(INVITATION_SURFACE_FIELDS),
        **deepcopy(INVITATION_LINEAGE_FIELDS),
    }
