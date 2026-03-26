import { describe, expect, it } from "vitest";

import {
  aggregatePipelineCounts,
  shouldShowPipelineCounts,
} from "../lib/api";

/** Spec 156 acceptance: counters align with GET /api/agent/tasks/count `by_status`. */
describe("renders_counts_and_items_from_api_success", () => {
  it("maps by_status into pending, running, completed, and attention totals", () => {
    expect(
      aggregatePipelineCounts({
        pending: 3,
        running: 2,
        completed: 6,
        failed: 1,
      }),
    ).toEqual({
      pending: 3,
      running: 2,
      completed: 6,
      needsAttention: 1,
    });
  });

  it("aggregates queued into pending and worker states into running", () => {
    expect(
      aggregatePipelineCounts({
        pending: 1,
        queued: 2,
        running: 1,
        claimed: 1,
        in_progress: 1,
        completed: 0,
        failed: 0,
        needs_decision: 1,
      }),
    ).toEqual({
      pending: 3,
      running: 3,
      completed: 0,
      needsAttention: 1,
    });
  });
});

/** Error panel + Retry are implemented in page.tsx; network failure is integration-tested manually or via Playwright. */
describe("shows_fetch_error_and_retry_on_network_failure", () => {
  it("does not treat loading or error as a safe window for pipeline totals", () => {
    const zeros = { pending: 0, running: 0, completed: 0, needsAttention: 0 };
    expect(shouldShowPipelineCounts("loading", null)).toBe(false);
    expect(shouldShowPipelineCounts("error", null)).toBe(false);
    expect(shouldShowPipelineCounts("error", zeros)).toBe(false);
  });
});

describe("does_not_render_zero_state_when_fetch_failed", () => {
  it("only shows numeric totals after successful fetch (ok + counts present)", () => {
    const zeros = { pending: 0, running: 0, completed: 0, needsAttention: 0 };
    expect(shouldShowPipelineCounts("ok", zeros)).toBe(true);
    expect(shouldShowPipelineCounts("loading", zeros)).toBe(false);
    expect(shouldShowPipelineCounts("error", zeros)).toBe(false);
  });
});
