"""Federation models for cross-instance data exchange."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class FederatedInstance(BaseModel):
    """A remote Coherence instance."""
    instance_id: str = Field(min_length=1, description="Unique ID of the remote instance")
    name: str = Field(min_length=1)
    endpoint_url: str = Field(min_length=1, description="Base URL of the remote API")
    public_key: Optional[str] = None  # For future signature verification
    registered_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    last_sync_at: Optional[str] = None
    trust_level: str = Field(default="pending", description="Trust level: unknown, pending, verified, trusted")


class FederatedPayload(BaseModel):
    """Data package from a remote instance."""
    source_instance_id: str = Field(min_length=1)
    timestamp: str
    lineage_links: list[dict] = Field(default_factory=list)
    usage_events: list[dict] = Field(default_factory=list)
    # Signature for future verification
    signature: Optional[str] = None


class FederationSyncResult(BaseModel):
    """Result of processing a federated payload."""
    source_instance_id: str
    links_received: int = 0
    events_received: int = 0
    governance_requests_created: int = 0
    accepted: int = 0
    rejected: int = 0
    errors: list[str] = Field(default_factory=list)
