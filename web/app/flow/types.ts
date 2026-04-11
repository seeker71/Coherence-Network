import { loadPublicWebConfig } from "@/lib/app-config";

// Resolved once at module load. The web config merges env vars
// (NEXT_PUBLIC_REPO_URL), api/config/api.json, and ~/.coherence-network/config.json,
// so deploys and dev environments can each point at their own fork.
const _repoBlob = loadPublicWebConfig().repoUrl;

// The tree URL is derived from the blob URL by swapping the final segment.
// /blob/main → /tree (branch is appended by callers that need it).
function _deriveTreeBase(blobUrl: string): string {
  return blobUrl.replace(/\/blob\/[^/]+$/, "/tree");
}

export const REPO_BLOB_MAIN = _repoBlob;
export const REPO_TREE = _deriveTreeBase(_repoBlob);

export type ValidationCounts = {
  pass: number;
  fail: number;
  pending: number;
};

export type FlowItem = {
  idea_id: string;
  idea_name: string;
  spec: { tracked: boolean; count: number; spec_ids: string[] };
  process: {
    tracked: boolean;
    evidence_count: number;
    task_ids: string[];
    thread_branches: string[];
    change_intents: string[];
    evidence_refs: string[];
    source_files: string[];
  };
  implementation: {
    tracked: boolean;
    lineage_link_count: number;
    lineage_ids: string[];
    implementation_refs: string[];
    runtime_events_count: number;
    runtime_total_ms: number;
    runtime_cost_estimate: number;
  };
  validation: {
    tracked: boolean;
    local: ValidationCounts;
    ci: ValidationCounts;
    deploy: ValidationCounts;
    e2e: ValidationCounts;
    phase_gate: { pass_count: number; blocked_count: number };
    public_endpoints: string[];
  };
  contributors: {
    tracked: boolean;
    total_unique: number;
    all: string[];
    registry_ids: string[];
    by_role: Record<string, string[]>;
  };
  contributions: {
    tracked: boolean;
    usage_events_count: number;
    measured_value_total: number;
    registry_contribution_count: number;
    registry_total_cost: number;
    contribution_ids: string[];
  };
  assets: {
    tracked: boolean;
    count: number;
    asset_ids: string[];
  };
  chain: {
    spec: string;
    process: string;
    implementation: string;
    validation: string;
    contributors: string;
    contributions: string;
    assets: string;
  };
  interdependencies: {
    blocked: boolean;
    blocking_stage: string | null;
    upstream_required: string[];
    downstream_blocked: string[];
    estimated_unblock_cost: number;
    estimated_unblock_value: number;
    unblock_priority_score: number;
    task_fingerprint: string | null;
    next_unblock_task: { task_type: string; direction: string } | null;
  };
  idea_signals: {
    value_gap: number;
    confidence: number;
    estimated_cost: number;
    potential_value: number;
    actual_value: number;
  };
};

export type FlowResponse = {
  summary: {
    ideas: number;
    with_spec: number;
    with_process: number;
    with_implementation: number;
    with_validation: number;
    with_contributors: number;
    with_contributions: number;
    blocked_ideas: number;
    queue_items: number;
  };
  unblock_queue: Array<{
    idea_id: string;
    idea_name: string;
    blocking_stage: string;
    upstream_required: string[];
    downstream_blocked: string[];
    estimated_unblock_cost: number;
    estimated_unblock_value: number;
    unblock_priority_score: number;
    task_fingerprint: string;
    task_type: string;
    direction: string;
    active_task?: { id: string; status: string; claimed_by?: string | null } | null;
  }>;
  items: FlowItem[];
};

export type Contributor = { id: string; name: string; type: string };
export type Contribution = { id: string; contributor_id: string; asset_id: string; timestamp: string };

export type FlowSearchParams = Promise<{
  idea_id?: string | string[];
  spec_id?: string | string[];
  contributor_id?: string | string[];
}>;
