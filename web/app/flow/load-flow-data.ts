import { getApiBase } from "@/lib/api";
import { fetchJsonOrNull } from "@/lib/fetch";
import type { Contributor, Contribution, FlowResponse } from "./types";

const defaultFlowResponse: FlowResponse = {
  summary: {
    ideas: 0,
    with_spec: 0,
    with_process: 0,
    with_implementation: 0,
    with_validation: 0,
    with_contributors: 0,
    with_contributions: 0,
    blocked_ideas: 0,
    queue_items: 0,
  },
  unblock_queue: [],
  items: [],
};

export async function loadData(): Promise<{
  flow: FlowResponse;
  contributors: Contributor[];
  contributions: Contribution[];
}> {
  return loadDataForIdea("");
}

export async function loadDataForIdea(ideaId: string): Promise<{
  flow: FlowResponse;
  contributors: Contributor[];
  contributions: Contribution[];
}> {
  const API = getApiBase();
  const flowParams = new URLSearchParams({ runtime_window_seconds: "86400" });
  if (ideaId) flowParams.set("idea_id", ideaId);
  const [flowData, contributorData, contributionData] = await Promise.all([
    fetchJsonOrNull<FlowResponse>(`${API}/api/inventory/flow?${flowParams.toString()}`, { cache: "no-store" }, 5000),
    fetchJsonOrNull<{ items: Contributor[] }>(`${API}/api/contributors`, { cache: "no-store" }, 5000),
    fetchJsonOrNull<{ items: Contribution[] }>(`${API}/api/contributions`, { cache: "no-store" }, 5000),
  ]);

  return {
    flow: flowData || defaultFlowResponse,
    contributors: contributorData?.items?.slice(0, 500) ?? [],
    contributions: contributionData?.items?.slice(0, 2000) ?? [],
  };
}
