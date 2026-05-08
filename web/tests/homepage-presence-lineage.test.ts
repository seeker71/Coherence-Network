import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const root = join(__dirname, "..");
const pageSource = readFileSync(join(root, "app/page.tsx"), "utf8");
const presenceWalk = JSON.parse(
  readFileSync(join(root, "content/presence-walk/en.json"), "utf8"),
) as {
  homePresence?: {
    order?: string[];
    traces?: Record<
      string,
      {
        traceLabel?: string;
        traceHref?: string;
        traceMetric?: string;
        traceSource?: string;
        traceWhy?: string;
        image?: string;
      }
    >;
  };
  presenceNodes?: {
    nodes?: Record<string, { image?: string }>;
  };
};
const localeFiles = ["en", "de", "es", "id"].map((locale) =>
  join(root, `messages/${locale}.json`),
);

function messageKeys(file: string): Set<string> {
  const parsed = JSON.parse(readFileSync(file, "utf8")) as {
    home?: Record<string, unknown>;
  };
  return new Set(Object.keys(parsed.home ?? {}));
}

describe("homepage presence lineage", () => {
  it("does not use stock, placeholder, or missing presence hero images", () => {
    expect(pageSource).not.toContain("images.unsplash.com");
    expect(pageSource).not.toContain("TODO: Replace");
    expect(pageSource).not.toContain("/presences/");
    expect(pageSource).not.toContain('href: "#"');
    expect(pageSource).not.toContain("FEATURED_PRESENCES");
    expect(pageSource).not.toContain("0Jq2Qv4o0vJq2Qv4o0vJq2Q");
  });

  it("draws home presences from presence data and trace pointers", () => {
    const homePresence = presenceWalk.homePresence;
    expect(pageSource).toContain("getHomePresenceTraceCards");
    expect(pageSource).toContain("await getHomePresenceTraceCards");
    expect(homePresence?.order).toEqual([
      "liquid-bloom",
      "bloomurian",
      "mose",
      "matias-de-stefano",
      "portal",
    ]);

    for (const slug of homePresence?.order ?? []) {
      const trace = homePresence?.traces?.[slug];
      expect(presenceWalk.presenceNodes?.nodes?.[slug], `${slug} missing node`).toBeTruthy();
      expect(trace?.traceLabel, `${slug} missing trace label`).toBeTruthy();
      expect(trace?.traceHref, `${slug} missing trace href`).toMatch(/^\/(api|people)\//);
      expect(trace?.traceMetric, `${slug} missing trace metric`).toBeTruthy();
      expect(trace?.traceSource, `${slug} missing trace source`).toMatch(/^(docs|web)\//);
      expect(trace?.traceWhy, `${slug} missing trace explanation`).toBeTruthy();
      expect(trace?.image, `${slug} missing home image`).toBeTruthy();
    }
  });

  it("uses public assets that exist in the repository", () => {
    const imageMatches = (presenceWalk.homePresence?.order ?? []).map(
      (slug) => presenceWalk.homePresence?.traces?.[slug]?.image,
    );

    expect(imageMatches).toEqual([
      "/visuals/brand/liquid-bloom-bg-center.jpg",
      "/people/bloomurian/hero.jpg",
      "/people/mose/hero.jpg",
      "/people/matias-de-stefano/hero.jpg",
      "/people/portal/hero.jpg",
    ]);

    for (const image of imageMatches) {
      expect(existsSync(join(root, "public", image))).toBe(true);
    }
  });

  it("keeps the living-lineage copy present in every supported locale", () => {
    const required = [
      "livingLineageEyebrow",
      "livingLineageHeadline",
      "livingLineageLede",
      "livingLineageCta",
      "livingLineageFootnote",
    ];

    for (const file of localeFiles) {
      const keys = messageKeys(file);
      for (const key of required) {
        expect(keys.has(key), `${file} missing home.${key}`).toBe(true);
      }
    }
  });

  it("keeps the English bundle broad enough for shared homepage chrome", () => {
    const english = JSON.parse(
      readFileSync(join(root, "messages/en.json"), "utf8"),
    ) as Record<string, unknown>;

    for (const namespace of ["common", "header", "nav", "homeBreath", "home"]) {
      expect(
        Object.prototype.hasOwnProperty.call(english, namespace),
        `messages/en.json missing ${namespace}`,
      ).toBe(true);
    }
  });
});
