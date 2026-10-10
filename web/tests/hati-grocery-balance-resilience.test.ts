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
