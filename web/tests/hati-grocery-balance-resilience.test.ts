import { describe, expect, it } from "vitest";

import {
  BALANCE_REFRESH_INTERVAL_MS,
  BALANCE_REQUEST_TIMEOUT_MS,
  BALANCE_RETRY_DELAYS_MS,
  baliCalendarDay,
  balanceCopyKey,
  isAuthorizationFailure,
  isConfirmedSheetBalance,
} from "@/lib/hati-grocery-balance";

describe("Hati grocery Sheet balance resilience", () => {
  it("names the first breath as connecting, not unavailable", () => {
    expect(balanceCopyKey("loading", false)).toBe("balanceConnecting");
    expect(balanceCopyKey("retrying", false)).toBe("balanceRetrying");
    expect(balanceCopyKey("unavailable", false)).toBe("balanceUnavailable");
  });

  it("keeps a last-confirmed balance visibly qualified during recovery", () => {
    expect(balanceCopyKey("retrying", true)).toBe("balanceLastConfirmed");
    expect(balanceCopyKey("unavailable", true)).toBe("balanceLastConfirmed");
    expect(balanceCopyKey("ready", true)).toBeNull();
  });

  it("accepts only a finite Sheet-owned balance as current", () => {
    expect(isConfirmedSheetBalance({ remaining_idr: 12_345, remaining_source: "sheet" })).toBe(true);
    expect(isConfirmedSheetBalance({ remaining_idr: null, remaining_source: "unavailable" })).toBe(false);
    expect(isConfirmedSheetBalance({ remaining_idr: Number.NaN, remaining_source: "sheet" })).toBe(false);
  });

  it("uses bounded attempts and a quiet ongoing recovery cadence", () => {
    expect(BALANCE_RETRY_DELAYS_MS).toEqual([0, 1_500]);
    expect(BALANCE_REQUEST_TIMEOUT_MS).toBeGreaterThan(13_000);
    expect(BALANCE_REFRESH_INTERVAL_MS).toBeGreaterThanOrEqual(60_000);
  });

  it("changes calendar day at Bali midnight independent of browser timezone", () => {
    expect(baliCalendarDay(Date.UTC(2026, 9, 9, 15, 59, 59))).toBe("2026-10-09");
    expect(baliCalendarDay(Date.UTC(2026, 9, 9, 16, 0, 0))).toBe("2026-10-10");
  });

  it("distinguishes stale identity from a Sheet outage", () => {
    expect(isAuthorizationFailure(401)).toBe(true);
    expect(isAuthorizationFailure(403)).toBe(true);
    expect(isAuthorizationFailure(503)).toBe(false);
  });
});

import {
  BALANCE_AGE_TICK_MS,
  confirmationAge,
  newEntryKey,
  withEntryKeys,
} from "@/lib/hati-grocery-balance";

describe("Hati grocery balance confirmation age", () => {
  const confirmed = Date.UTC(2026, 9, 24, 10, 0, 0);
  const iso = new Date(confirmed).toISOString();

  it("says how old the last confirmed balance is in the unit a person would use", () => {
    expect(confirmationAge(iso, confirmed + 20_000)).toEqual({ unit: "now" });
    expect(confirmationAge(iso, confirmed + 3 * 60_000 + 5_000)).toEqual({ unit: "minutes", count: 3 });
    expect(confirmationAge(iso, confirmed + 2 * 3_600_000)).toEqual({ unit: "hours", count: 2 });
    expect(confirmationAge(iso, confirmed + 49 * 3_600_000)).toEqual({ unit: "days", count: 2 });
  });

  it("has no age before the sheet has confirmed anything", () => {
    expect(confirmationAge(null, confirmed)).toBeNull();
    expect(confirmationAge(undefined, confirmed)).toBeNull();
    expect(confirmationAge("not a date", confirmed)).toBeNull();
  });

  it("reads a confirmation from the future as just now, never a negative age", () => {
    expect(confirmationAge(iso, confirmed - 90_000)).toEqual({ unit: "now" });
  });

  it("keeps the age counting more often than the balance refreshes", () => {
    expect(BALANCE_AGE_TICK_MS).toBeLessThan(60_000);
  });
});

describe("Hati grocery draft keys", () => {
  it("mints a distinct key per draft in the server's accepted shape", () => {
    const keys = new Set(Array.from({ length: 50 }, () => newEntryKey()));
    expect(keys.size).toBe(50);
    for (const key of keys) expect(key).toMatch(/^[A-Za-z0-9._:-]{8,80}$/);
  });

  it("gives an older queued draft a key once and leaves keyed drafts untouched", () => {
    const keyed = [{ amount: "160", entry_key: "draft-already-keyed" }];
    expect(withEntryKeys(keyed)).toBe(keyed);

    const legacy = [{ amount: "160" }, { amount: "204", entry_key: "" }];
    const migrated = withEntryKeys(legacy);
    expect(migrated).not.toBe(legacy);
    expect(migrated.map((d) => d.amount)).toEqual(["160", "204"]);
    expect(migrated.every((d) => /^[A-Za-z0-9._:-]{8,80}$/.test(d.entry_key))).toBe(true);
    expect(migrated[0].entry_key).not.toBe(migrated[1].entry_key);
  });
});
