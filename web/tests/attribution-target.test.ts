import { describe, expect, it } from "vitest";

import { attributionTargetFromHref } from "@/lib/attribution-target";

describe("attributionTargetFromHref", () => {
  it("ignores hash-only links", () => {
    expect(attributionTargetFromHref("#main-content")).toBeNull();
  });

  it("maps root and nested page routes to page entity ids", () => {
    expect(attributionTargetFromHref("/")).toEqual({
      entityType: "page",
      entityId: "home",
      assetId: "page:home",
    });
    expect(attributionTargetFromHref("/feed/you?tab=now")).toEqual({
      entityType: "page",
      entityId: "feed-you",
      assetId: "page:feed-you",
    });
  });

  it("maps typed content routes to their source entities", () => {
    expect(attributionTargetFromHref("/ideas/oss-interface-alignment")).toEqual({
      entityType: "idea",
      entityId: "oss-interface-alignment",
      assetId: "oss-interface-alignment",
    });
    expect(attributionTargetFromHref("/vision/lc-pulse")).toEqual({
      entityType: "concept",
      entityId: "lc-pulse",
      assetId: "lc-pulse",
      conceptId: "lc-pulse",
    });
    expect(attributionTargetFromHref("/meet/concept/lc-nourishing")).toEqual({
      entityType: "concept",
      entityId: "lc-nourishing",
      assetId: "lc-nourishing",
      conceptId: "lc-nourishing",
    });
    expect(attributionTargetFromHref("/specs/006-overnight-backlog")).toEqual({
      entityType: "spec",
      entityId: "006-overnight-backlog",
      assetId: "006-overnight-backlog",
    });
  });
});
