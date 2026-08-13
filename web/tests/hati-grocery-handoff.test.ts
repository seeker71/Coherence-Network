import { describe, expect, it } from "vitest";

import {
  groceryHandoffHref,
  hatiSuciRecoveryHref,
  requestsGroceryReturn,
} from "@/lib/hati-grocery-handoff";

describe("Hati grocery identity handoff", () => {
  it("carries a validated household token to the fixed grocery origin", () => {
    expect(
      groceryHandoffHref("resident token", {
        hostname: "coherencycoin.com",
        origin: "https://coherencycoin.com",
      }),
    ).toBe("https://app.hati.earth/?token=resident+token");
  });

  it("keeps local development on the local server", () => {
    expect(
      groceryHandoffHref("local", {
        hostname: "localhost",
        origin: "http://localhost:3119",
      }),
    ).toBe("http://localhost:3119/grocery?token=local");
  });

  it("keeps a LAN or preview host on its own grocery route", () => {
    expect(
      groceryHandoffHref("phone", {
        hostname: "192.168.1.20",
        origin: "http://192.168.1.20:3000",
      }),
    ).toBe("http://192.168.1.20:3000/grocery?token=phone");
    expect(
      groceryHandoffHref("v6", {
        hostname: "[::1]",
        origin: "http://[::1]:3000",
      }),
    ).toBe("http://[::1]:3000/grocery?token=v6");
  });

  it("returns a disconnected app visit through the canonical Hati Suci door", () => {
    expect(
      hatiSuciRecoveryHref({
        hostname: "app.hati.earth",
        origin: "https://app.hati.earth",
      }),
    ).toBe("https://coherencycoin.com/hati-suci?to=grocery");
  });

  it("accepts only the fixed grocery return intent", () => {
    expect(requestsGroceryReturn("?to=grocery")).toBe(true);
    expect(requestsGroceryReturn("?to=https://example.com")).toBe(false);
    expect(requestsGroceryReturn("?return=grocery")).toBe(false);
  });
});
