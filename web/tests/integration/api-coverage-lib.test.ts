import { describe, expect, it } from "vitest";

import { buildProbeUrl } from "../../app/api-coverage/lib";

describe("api coverage probe URL builder", () => {
  it("does not double-prefix paths that already include /api", () => {
    expect(buildProbeUrl("/api/assets")).toMatch(/\/api\/assets$/);
    expect(buildProbeUrl("/api/assets")).not.toMatch(/\/api\/api\/assets$/);
  });

  it("adds the /api prefix for canonical route paths", () => {
    expect(buildProbeUrl("/gates/pr-to-public")).toMatch(/\/api\/gates\/pr-to-public\?branch=main$/);
  });
});
