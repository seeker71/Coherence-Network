import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = process.cwd();

describe("anonymous meeting trace client", () => {
  it("is mounted in the root layout and sends only opaque continuity keys", () => {
    const layout = readFileSync(join(root, "app/layout.tsx"), "utf8");
    const source = readFileSync(join(root, "components/AnonymousMeetingTrace.tsx"), "utf8");

    expect(layout).toContain("<AnonymousMeetingTrace />");
    expect(source).toContain("/api/meetings/anonymous-traces");
    expect(source).toContain("ensureFingerprint()");
    expect(source).toContain("sessionStorage");
    expect(source).toContain("duration_ms");
    expect(source).toContain("started_at");
    expect(source).toContain("ended_at");
    expect(source).toContain("referrer_domain");
    expect(source).toContain("document.referrer");
    expect(source).toContain("referrer.hostname");
    expect(source).not.toContain("geolocation");
    expect(source).not.toContain("navigator.userAgent");
  });
});
