import {
  existsSync,
  readFileSync,
  readdirSync,
  statSync,
} from "node:fs";
import { join, relative, resolve, sep } from "node:path";

import { describe, expect, it } from "vitest";

const WEB_ROOT = resolve(__dirname, "..");
const APP_ROOT = join(WEB_ROOT, "app");
const PUBLIC_ROOT = join(WEB_ROOT, "public");

function walk(directory: string): string[] {
  return readdirSync(directory).flatMap((name) => {
    const path = join(directory, name);
    return statSync(path).isDirectory() ? walk(path) : [path];
  });
}

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function routePattern(file: string): RegExp {
  const directory = relative(APP_ROOT, resolve(file, ".."));
  const segments = directory
    .split(sep)
    .filter((segment) => segment && !(segment.startsWith("(") && segment.endsWith(")")))
    .map((segment) => {
      if (/^\[\[\.\.\..+\]\]$/.test(segment)) return ".*";
      if (/^\[\.\.\..+\]$/.test(segment)) return ".+";
      if (/^\[.+\]$/.test(segment)) return "[^/]+";
      return escapeRegex(segment);
    });
  return new RegExp(`^/${segments.join("/")}$`);
}

const routePatterns = walk(APP_ROOT)
  .filter((file) => /\/(?:page\.tsx|route\.ts)$/.test(file))
  .map(routePattern);

const redirectSources = new Set(
  Array.from(
    readFileSync(join(WEB_ROOT, "next.config.ts"), "utf8").matchAll(
      /source:\s*["']([^"']+)["']/g,
    ),
    (match) => match[1],
  ),
);

function cleanPath(href: string): string {
  return href.split("#", 1)[0].split("?", 1)[0];
}

function resolvesInternally(href: string): boolean {
  const pathname = cleanPath(href);
  if (!pathname || pathname.startsWith("/api/") || pathname.startsWith("/_next/")) {
    return true;
  }
  if (redirectSources.has(pathname)) return true;
  if (existsSync(join(PUBLIC_ROOT, pathname.slice(1)))) return true;
  return routePatterns.some((pattern) => pattern.test(pathname));
}

function lineNumber(source: string, offset: number): number {
  return source.slice(0, offset).split("\n").length;
}

function sourceLinkMisses(): string[] {
  const misses: string[] = [];
  const navigationPatterns = [
    /\bhref\s*(?:=|:)\s*(?:\{\s*)?["'](\/[^"'`]*)["']/g,
    /\b(?:redirect|router\.(?:push|replace))\(\s*["'](\/[^"'`]*)["']/g,
  ];

  for (const file of walk(APP_ROOT).filter((path) => /\.[jt]sx?$/.test(path))) {
    const source = readFileSync(file, "utf8");
    for (const pattern of navigationPatterns) {
      for (const match of source.matchAll(pattern)) {
        const href = match[1];
        if (!resolvesInternally(href)) {
          misses.push(
            `${relative(WEB_ROOT, file)}:${lineNumber(source, match.index)} -> ${href}`,
          );
        }
      }
    }
  }
  return misses;
}

function markdownLinkMisses(): string[] {
  const roots = [join(WEB_ROOT, "messages"), join(WEB_ROOT, "content")];
  const misses: string[] = [];
  for (const root of roots) {
    for (const file of walk(root).filter((path) => path.endsWith(".json"))) {
      const source = readFileSync(file, "utf8");
      for (const match of source.matchAll(/\]\((\/[^)\s]+)\)/g)) {
        const href = match[1];
        if (!resolvesInternally(href)) {
          misses.push(
            `${relative(WEB_ROOT, file)}:${lineNumber(source, match.index)} -> ${href}`,
          );
        }
      }
    }
  }
  return misses;
}

describe("internal page links", () => {
  it("keeps literal application navigation attached to a page, route, asset, or redirect", () => {
    expect(sourceLinkMisses()).toEqual([]);
  });

  it("keeps localized markdown navigation attached to the route tree", () => {
    expect(markdownLinkMisses()).toEqual([]);
  });

  it("preserves the two retired ontology child URLs", () => {
    expect(redirectSources).toContain("/ontology/contribute");
    expect(redirectSources).toContain("/ontology/stats");
  });
});
