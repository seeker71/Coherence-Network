import fs from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const WEB_ROOT = path.resolve(__dirname, "..");

function readWebFile(relativePath: string): string {
  return fs.readFileSync(path.join(WEB_ROOT, relativePath), "utf8");
}

describe("health proxy route-goal telemetry", () => {
  const source = readWebFile("app/api/health-proxy/route.ts");

  it("attributes web_api route pressure to the upstream API endpoint", () => {
    expect(source).toContain('const HEALTH_PROXY_ENDPOINT = "/api/health-proxy"');
    expect(source).toContain('const HEALTH_UPSTREAM_ENDPOINT = "/api/health/pulse"');
    expect(source).toMatch(/endpoint:\s*HEALTH_UPSTREAM_ENDPOINT/);
    expect(source).toMatch(/raw_endpoint:\s*HEALTH_PROXY_ENDPOINT/);
  });

  it("keeps continuous proxy polling off the deep native-proof health lane", () => {
    expect(source).toContain('const HEALTH_UPSTREAM_ENDPOINT = "/api/health/pulse"');
    expect(source).not.toContain('const HEALTH_UPSTREAM_ENDPOINT = "/api/health"');
  });

  it("keeps the proxy shell visible as metadata rather than the promotion target", () => {
    expect(source).toMatch(/web_route:\s*HEALTH_PROXY_ENDPOINT/);
    expect(source).toMatch(/upstream_endpoint:\s*HEALTH_UPSTREAM_ENDPOINT/);
  });

  it("does not amplify an upstream failure with a second API telemetry request", () => {
    expect(source).toMatch(/if \(statusCode >= 500\) return;/);
  });
});
