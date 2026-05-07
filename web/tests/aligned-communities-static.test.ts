import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = process.cwd();

describe("aligned community detail routes", () => {
  it("does not present care institutions as living-community design examples", () => {
    const detailSource = readFileSync(
      join(root, "app/vision/aligned/[communityId]/page.tsx"),
      "utf8",
    );

    expect(detailSource).not.toContain("bumi-sehat");
    expect(detailSource).not.toContain("Bumi Sehat");
    expect(detailSource).not.toContain("birth clinic");
    expect(detailSource).not.toContain("community organism for the threshold of birth");
  });
});
