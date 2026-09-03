import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  loadStewardshipPage,
  rewriteStewardshipLinks,
  stewardshipHrefForSource,
} from "../lib/stewardship-documents";

const REPO_ROOT = resolve(__dirname, "..", "..");
const STEWARDSHIP_ROOT = join(REPO_ROOT, "docs", "stewardship");

function walk(directory: string): string[] {
  return readdirSync(directory).flatMap((name) => {
    const path = join(directory, name);
    return statSync(path).isDirectory() ? walk(path) : [path];
  });
}

function segmentsFromHref(href: string): string[] {
  return href
    .split("#", 1)[0]
    .replace(/^\/stewardship\/?/, "")
    .split("/")
    .filter(Boolean);
}

describe("public stewardship pages", () => {
  it("ships the public source corpus and production probes", () => {
    expect(readFileSync(join(REPO_ROOT, "Dockerfile.web"), "utf8")).toContain(
      "COPY docs/stewardship ./docs/stewardship",
    );

    const deployVerifier = readFileSync(
      join(REPO_ROOT, "scripts", "verify_web_api_deploy.sh"),
      "utf8",
    );
    expect(deployVerifier).toContain(
      "https://hati.earth/stewardship/registry",
    );
    expect(deployVerifier).toContain(
      "https://hati.earth/stewardship/onboarded-assets/2026-04-29-tesla-model-3-longmont",
    );

    for (const workflow of [
      "hostinger-auto-deploy.yml",
      "public-deploy-contract.yml",
    ]) {
      expect(
        readFileSync(
          join(REPO_ROOT, ".github", "workflows", workflow),
          "utf8",
        ),
      ).toContain("- 'docs/stewardship/**'");
    }
  });

  it("serves both stewardship links emitted by the Urs profile", () => {
    const content = readFileSync(
      join(REPO_ROOT, "docs", "presence-content", "urs.json"),
      "utf8",
    );
    const hrefs = Array.from(
      content.matchAll(/\]\((\/stewardship\/[^)]+)\)/g),
      (match) => match[1],
    );

    expect(hrefs).toContain("/stewardship/registry/");
    expect(hrefs).toContain(
      "/stewardship/onboarded-assets/2026-04-29-tesla-model-3-longmont",
    );
    for (const href of hrefs) {
      expect(loadStewardshipPage(segmentsFromHref(href)), href).not.toBeNull();
    }
  });

  it("keeps every relative stewardship document link inside a real route", () => {
    for (const file of walk(STEWARDSHIP_ROOT).filter((path) =>
      path.endsWith(".md"),
    )) {
      const sourcePath = relative(STEWARDSHIP_ROOT, file).replaceAll("\\", "/");
      const markdown = readFileSync(file, "utf8");
      const rewritten = rewriteStewardshipLinks(markdown, sourcePath);
      const internalHrefs = Array.from(
        rewritten.matchAll(/\]\((\/stewardship[^)#]*(?:#[^)]*)?)\)/g),
        (match) => match[1],
      );
      for (const href of internalHrefs) {
        expect(
          loadStewardshipPage(segmentsFromHref(href)),
          `${sourcePath} -> ${href}`,
        ).not.toBeNull();
      }
    }
  });

  it("normalizes document and directory links and rejects traversal", () => {
    expect(stewardshipHrefForSource("registry/README.md")).toBe(
      "/stewardship/registry",
    );
    expect(
      rewriteStewardshipLinks(
        "[money](financial.md) [cars](../onboarded-assets/)",
        "registry/README.md",
      ),
    ).toBe(
      "[money](/stewardship/registry/financial) [cars](/stewardship/onboarded-assets)",
    );
    expect(
      loadStewardshipPage(["..", "presence-content", "urs.json"]),
    ).toBeNull();
    expect(loadStewardshipPage(["not-a-record"])).toBeNull();
  });
});
