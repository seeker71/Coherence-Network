import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const root = join(__dirname, "..");

describe("Bali land design path", () => {
  it("keeps the living compound visible from the public entry surfaces", () => {
    const homeSource = readFileSync(join(root, "app/page.tsx"), "utf8");
    const comeInSource = readFileSync(join(root, "app/come-in/page.tsx"), "utf8");

    expect(homeSource).toContain('href="/silence/built"');
    expect(homeSource).toContain("land stewards");
    expect(comeInSource).toContain('href="/silence/built"');
    expect(comeInSource).toContain("Meet the land draft");
  });

  it("keeps the localized come-in door keys present", () => {
    for (const locale of ["en", "de", "es", "id"]) {
      const messages = JSON.parse(
        readFileSync(join(root, `messages/${locale}.json`), "utf8"),
      ) as { comeIn?: Record<string, unknown> };

      for (const key of ["doorBuiltEyebrow", "doorBuiltLabel", "doorBuiltBody"]) {
        expect(
          Object.prototype.hasOwnProperty.call(messages.comeIn ?? {}, key),
          `${locale} missing comeIn.${key}`,
        ).toBe(true);
      }
    }
  });

  it("does not route the land path through Bumi Sehat as a community example", () => {
    const alignedSource = readFileSync(
      join(root, "app/vision/aligned/[communityId]/page.tsx"),
      "utf8",
    );
    const publicEntrySource = [
      readFileSync(join(root, "app/page.tsx"), "utf8"),
      readFileSync(join(root, "app/come-in/page.tsx"), "utf8"),
      readFileSync(join(root, "app/silence/built/page.tsx"), "utf8"),
    ].join("\n");

    expect(alignedSource).not.toContain("Bumi Sehat");
    expect(publicEntrySource).not.toContain("Bumi Sehat");
  });
});
