"""All ORM models registered on the unified Base.

Import this module to ensure all tables are registered before calling
unified_db.ensure_schema().

This module re-exports models from each domain so that existing service
code can import from here or continue importing from original locations
(which now delegate to unified_db.Base).
"""

from __future__ import annotations

# Import the unified Base
from app.services.unified_db import Base  # noqa: F401

# ---------------------------------------------------------------------------
# Idea Registry models
# ---------------------------------------------------------------------------
from app.services.idea_registry_service import (  # noqa: F401
    IdeaRecord,
    IdeaQuestionRecord,
    RegistryMetaRecord,
)

# ---------------------------------------------------------------------------
# Spec Registry + Governance models
# ---------------------------------------------------------------------------
from app.services.spec_registry_service import SpecRegistryRecord  # noqa: F401
from app.services.traceability_links_service import (  # noqa: F401
    TraceabilityImplementationLinkRecord,
)
from app.services.governance_service import (  # noqa: F401
    ChangeRequestRecord,
    ChangeRequestVoteRecord,
)

# ---------------------------------------------------------------------------
# Commit Evidence models
# ---------------------------------------------------------------------------
from app.services.commit_evidence_service import CommitEvidenceRecord  # noqa: F401

# ---------------------------------------------------------------------------
# Telemetry Persistence models
# ---------------------------------------------------------------------------
from app.services.telemetry_persistence.models import (  # noqa: F401
    TelemetryMetaRecord,
    AutomationUsageSnapshotRecord,
    FrictionEventRecord,
    ExternalToolUsageEventRecord,
    TaskMetricRecord,
)

# ---------------------------------------------------------------------------
# Value Lineage models
# ---------------------------------------------------------------------------
from app.services.value_lineage_service import (  # noqa: F401
    LineageLinkRecord,
    UsageEventRecord,
)

# ---------------------------------------------------------------------------
# Contribution Ledger models
# ---------------------------------------------------------------------------
from app.services.contribution_ledger_service import ContributionLedgerRecord  # noqa: F401

# ---------------------------------------------------------------------------
# Federation models
# ---------------------------------------------------------------------------
from app.services.federation_service import (  # noqa: F401
    FederatedInstanceRecord,
    FederationNodeRecord,
    FederationSyncHistoryRecord,
    NodeMeasurementSummaryRecord,
    NodeStrategyBroadcastRecord,
)

# ---------------------------------------------------------------------------
# Postgres graph-store models (contributions, contributors, assets)
# ---------------------------------------------------------------------------
from app.adapters.postgres_models import (  # noqa: F401
    ContributionModel,
    ContributorModel,
    AssetModel,
)

# ---------------------------------------------------------------------------
# Contributor Identity models
# ---------------------------------------------------------------------------
from app.services.contributor_identity_service import ContributorIdentityRecord  # noqa: F401

# Graph models (Node + Edge universal data layer)
from app.models.graph import Node, Edge  # noqa: F401
