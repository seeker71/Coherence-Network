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
from app.services.repo_credential_service import RepoCredentialRecord  # noqa: F401

# Pipeline Policy models
from app.services.pipeline_policy_service import PipelinePolicyRecord  # noqa: F401

# CC Economics models (treasury ledger + stake positions)
from app.services.cc_treasury_service import (  # noqa: F401
    TreasuryLedgerEntry,
    StakePositionRow,
)

# Graph models (Node + Edge universal data layer)
from app.models.graph import Node, Edge  # noqa: F401

# Read tracking + view event models
from app.services.read_tracking_service import AssetReadDaily, AssetViewEvent  # noqa: F401

# Wallet models
from app.services.wallet_service import WalletRecord  # noqa: F401

# Reward policy models
from app.services.reward_policy_service import RewardPolicyRecord  # noqa: F401

# Multilingual concept views + glossary
from app.services.translation_cache_service import (  # noqa: F401
    EntityViewRecord,
    GlossaryEntryRecord,
)

# Community voices — lived experience on concepts
from app.services.concept_voice_service import ConceptVoiceRecord  # noqa: F401

# Reactions — emoji + comment on any entity
from app.services.reaction_service import ReactionRecord  # noqa: F401
