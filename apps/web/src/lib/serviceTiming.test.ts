import { describe, expect, it } from "vitest";

import { elapsedTime, requiredDateSignal } from "./serviceTiming";

describe("service timing labels", () => {
  const now = new Date("2026-08-08T12:00:00Z");

  it.each([
    ["2026-08-08T11:59:30Z", "less than a minute"],
    ["2026-08-08T11:59:00Z", "1 minute"],
    ["2026-08-08T11:30:00Z", "30 minutes"],
    ["2026-08-08T11:00:00Z", "1 hour"],
    ["2026-08-08T09:00:00Z", "3 hours"],
    ["2026-08-07T12:00:00Z", "1 day"],
    ["2026-08-03T12:00:00Z", "5 days"],
    ["2026-08-09T12:00:00Z", "less than a minute"],
  ])("formats elapsed time from %s", (start, expected) => {
    expect(elapsedTime(start, now)).toBe(expected);
  });

  it.each([
    ["2026-08-06", "Required date passed by 2 days", "late", -2],
    ["2026-08-07", "Required date passed by 1 day", "late", -1],
    ["2026-08-08", "Required today", "attention", 0],
    ["2026-08-09", "Required tomorrow", "attention", 1],
    ["2026-08-11", "Required in 3 days", "attention", 3],
    ["2026-08-12", "Required in 4 days", "neutral", 4],
  ] as const)("describes required date %s", (date, label, tone, daysRemaining) => {
    expect(requiredDateSignal(date, now)).toEqual({ daysRemaining, label, tone });
  });
});
