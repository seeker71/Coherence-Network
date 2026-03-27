import fs from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { ECOSYSTEM_LINKS, resolveEcosystemLink } from "@/lib/ecosystem-links";

const WEB_ROOT = path.resolve(__dirname, "../..");

function readWebFile(relativePath: string): string {
  return fs.readFileSync(path.join(WEB_ROOT, relativePath), "utf8");
}

describe("ecosystem links contract", () => {
  it("renders all required ecosystem rows in static config", () => {
    const ids = ECOSYSTEM_LINKS.map((link) => link.id);
    expect(ids).toContain("github");
    expect(ids).toContain("npm");
    expect(ids).toContain("cli-install");
    expect(ids).toContain("api-docs");
    expect(ids).toContain("openclaw");
  });

  it("keeps ids unique to avoid ambiguous rendering", () => {
    const ids = ECOSYSTEM_LINKS.map((link) => link.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe("ecosystem discoverability and safe links", () => {
  it("exposes ecosystem entry point in global footer", () => {
    const footerSource = readWebFile("components/site-footer.tsx");
    expect(footerSource.includes('href="/ecosystem"')).toBe(true);
    expect(footerSource.includes(">Ecosystem<")).toBe(true);
  });

  it("uses safe target and rel for external links", () => {
    const pageSource = readWebFile("app/ecosystem/page.tsx");
    expect(pageSource.includes('target="_blank"')).toBe(true);
    expect(pageSource.includes('rel="noreferrer noopener"')).toBe(true);
  });
});

describe("unavailable link behavior", () => {
  it("resolves missing URL as unavailable without dropping the row contract", () => {
    const unresolved = resolveEcosystemLink({
      id: "missing-url",
      name: "Missing",
      purpose: "Should show unavailable",
      type: "docs",
      url: "",
    });
    expect(unresolved.status).toBe("unavailable");
    expect(unresolved.url).toBeNull();
  });

  it("includes non-clickable unavailable helper text in page template", () => {
    const pageSource = readWebFile("app/ecosystem/page.tsx");
    expect(pageSource.includes("Link not configured yet")).toBe(true);
    expect(pageSource.includes('aria-disabled="true"')).toBe(true);
  });
});
