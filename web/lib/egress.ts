const UI_RUNTIME_WINDOW_SECONDS = 21600;
const UI_RUNTIME_SUMMARY_SECONDS = 21600;
const UI_SYSTEM_LINEAGE_LIMITS = {
  lineage_link_limit: 120,
  usage_event_limit: 250,
  runtime_event_limit: 300,
} as const;
const UI_FLOW_LIMITS = {
  contributor_limit: 150,
  contribution_limit: 400,
  asset_limit: 200,
  spec_limit: 120,
  lineage_link_limit: 120,
  usage_event_limit: 300,
  commit_evidence_limit: 120,
  runtime_event_limit: 300,
} as const;

export const UI_CONTRIBUTOR_LIMIT = 150;
export const UI_CONTRIBUTION_LIMIT = 400;
export const UI_RUNTIME_EVENTS_LIMIT = 120;
export const UI_RUNTIME_WINDOW = UI_RUNTIME_WINDOW_SECONDS;
export const UI_RUNTIME_SUMMARY_WINDOW = UI_RUNTIME_SUMMARY_SECONDS;

function setNumeric(params: URLSearchParams, key: string, value: number): void {
  params.set(key, String(Math.max(1, Math.trunc(value))));
}

export function buildSystemLineageSearchParams(
  runtimeWindowSeconds: number = UI_RUNTIME_WINDOW,
): URLSearchParams {
  const params = new URLSearchParams();
  setNumeric(params, "runtime_window_seconds", runtimeWindowSeconds);
  for (const [key, value] of Object.entries(UI_SYSTEM_LINEAGE_LIMITS)) {
    setNumeric(params, key, value);
  }
  return params;
}

export function buildFlowSearchParams(options: {
  ideaId?: string;
  runtimeWindowSeconds?: number;
} = {}): URLSearchParams {
  const params = new URLSearchParams();
  setNumeric(params, "runtime_window_seconds", options.runtimeWindowSeconds ?? UI_RUNTIME_WINDOW);
  for (const [key, value] of Object.entries(UI_FLOW_LIMITS)) {
    setNumeric(params, key, value);
  }
  const ideaId = (options.ideaId || "").trim();
  if (ideaId) {
    params.set("idea_id", ideaId);
  }
  return params;
}

export function buildRuntimeSummarySearchParams(
  seconds: number = UI_RUNTIME_SUMMARY_WINDOW,
): URLSearchParams {
  const params = new URLSearchParams();
  setNumeric(params, "seconds", seconds);
  return params;
}
