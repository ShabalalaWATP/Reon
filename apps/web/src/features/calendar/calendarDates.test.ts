import { describe, expect, it } from "vitest";

import {
  addDays,
  calendarRange,
  calendarTitle,
  localInput,
  moveAnchor,
  sameDay,
} from "./calendarDates";

describe("calendar date boundaries", () => {
  const wednesday = new Date(2026, 7, 5, 14, 30);

  it("uses Monday-first bounded ranges for each calendar view", () => {
    expect(calendarRange(wednesday, "week").start.getDay()).toBe(1);
    expect(calendarRange(wednesday, "week").start.getHours()).toBe(0);
    expect(calendarRange(wednesday, "month").end.getTime() - calendarRange(wednesday, "month").start.getTime()).toBe(42 * 86_400_000);
    expect(calendarRange(wednesday, "week").end.getTime() - calendarRange(wednesday, "week").start.getTime()).toBe(7 * 86_400_000);
    expect(calendarRange(wednesday, "agenda").end.getTime() - calendarRange(wednesday, "agenda").start.getTime()).toBe(30 * 86_400_000);
    expect(calendarRange(wednesday, "month").start.getDay()).toBe(1);
  });

  it("moves each view by its natural period without changing the input", () => {
    expect(moveAnchor(wednesday, "month", 1).getMonth()).toBe(8);
    expect(moveAnchor(wednesday, "month", -1).getMonth()).toBe(6);
    expect(moveAnchor(wednesday, "week", 1).getDate()).toBe(12);
    expect(moveAnchor(wednesday, "agenda", -1).getMonth()).toBe(6);
    expect(wednesday.getDate()).toBe(5);
  });

  it("formats titles, inputs and day comparisons deterministically", () => {
    expect(calendarTitle(wednesday, "month")).toBe("August 2026");
    expect(calendarTitle(wednesday, "week")).toContain("Aug 2026");
    expect(calendarTitle(wednesday, "agenda")).toContain("Sept 2026");
    expect(sameDay(wednesday, new Date(2026, 7, 5, 23, 59))).toBe(true);
    expect(sameDay(wednesday, addDays(wednesday, 1))).toBe(false);
    expect(localInput(wednesday)).toMatch(/^2026-08-05T14:30$/);
  });
});
