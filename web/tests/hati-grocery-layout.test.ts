import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const source = readFileSync(join(__dirname, "../app/grocery/page.tsx"), "utf8");

describe("Hati grocery balance layout", () => {
  it("places the phone balance before the entry pad", () => {
    const phoneBalance = source.indexOf('className="mt-6 lg:hidden"');
    const entryPad = source.indexOf('className="mt-3 grid gap-6 lg:mt-6');

    expect(phoneBalance).toBeGreaterThan(-1);
    expect(entryPad).toBeGreaterThan(phoneBalance);
  });

  it("keeps the laptop balance in the ledger column", () => {
    expect(source).toContain('className="mb-3 hidden lg:block"');
  });
});
