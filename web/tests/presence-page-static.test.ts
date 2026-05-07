import fs from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const WEB_ROOT = path.resolve(__dirname, "..");

function readWebFile(relativePath: string): string {
  return fs.readFileSync(path.join(WEB_ROOT, relativePath), "utf8");
}

describe("external presence profile page", () => {
  const source = readWebFile("components/presence/PresencePage.tsx");
  const personPageSource = readWebFile("app/people/[id]/page.tsx");

  it("surfaces richer external profile sections", () => {
    expect(source).toContain("At a glance");
    expect(source).toContain("Presence map");
    expect(source).toContain("Entry points");
  });

  it("keeps the external source and graph node as first-class exits", () => {
    expect(source).toContain("identity.canonical_url");
    expect(source).toContain("/nodes/");
  });

  it("labels concept portals cleanly when they render as presences", () => {
    expect(personPageSource).toContain('concept: "Concept"');
  });
});
