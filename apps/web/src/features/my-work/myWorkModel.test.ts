import { describe, expect, it } from "vitest";

import { formatActionDate, freshnessMessage, humaniseCode, safeWorkspaceHref } from "./myWorkModel";

describe("my work presentation policy", () => {
  it("permits only known relative workspace links", () => {
    expect(safeWorkspaceHref("/requests/item?tab=history#event")).toBe(
      "/requests/item?tab=history#event",
    );
    expect(safeWorkspaceHref("/notifications")).toBe("/notifications");
    expect(safeWorkspaceHref("requests/item")).toBeNull();
    expect(safeWorkspaceHref("//attacker.test/requests")).toBeNull();
    expect(safeWorkspaceHref("https://attacker.test/requests")).toBeNull();
    expect(safeWorkspaceHref("/requests\\item")).toBeNull();
    expect(safeWorkspaceHref("/unknown/item")).toBeNull();
    expect(safeWorkspaceHref(null)).toBeNull();
  });

  it("humanises codes and formats nullable dates", () => {
    expect(humaniseCode("LEAD_REVIEW")).toBe("Lead review");
    expect(formatActionDate(null)).toBe("Not set");
    expect(formatActionDate("2026-08-07T09:00:00Z")).toContain("07 Aug 2026");
  });

  it("explains every projection freshness state", () => {
    const base = { projectedAt: null, sourceChangedAt: null, lagSeconds: null, pendingCount: 0 };
    expect(freshnessMessage({ ...base, status: "CURRENT" })).toBeNull();
    expect(freshnessMessage({ ...base, status: "CURRENT", pendingCount: 1 })).toContain(
      "1 update is",
    );
    expect(freshnessMessage({ ...base, status: "STALE", pendingCount: 2 })).toContain(
      "2 updates are",
    );
    expect(freshnessMessage({ ...base, status: "DEGRADED" })).toContain("Live updates");
    expect(freshnessMessage({ ...base, status: "STALE" })).toContain("out of date");
    expect(freshnessMessage({ ...base, status: "STALE", lagSeconds: 0 })).toContain(
      "1 minute behind",
    );
    expect(freshnessMessage({ ...base, status: "STALE", lagSeconds: 61 })).toContain("2 minutes");
  });
});
