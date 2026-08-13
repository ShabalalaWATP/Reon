import { describe, expect, it } from "vitest";

import {
  journeyState,
  lifecycleDescription,
  lifecycleLabels,
  lifecyclePhase,
  routePosition,
} from "./trackingPresentation";

describe("tracking lifecycle presentation", () => {
  it.each([
    ["TRIAGE_REVIEW", 0],
    ["IN_PROGRESS", 1],
    ["REWORK_REQUIRED", 2],
    ["READY_FOR_RELEASE", 3],
    ["COMPLETED", 4],
  ] as const)("maps %s to lifecycle phase %s", (status, phase) => {
    expect(lifecyclePhase(status)).toBe(phase);
  });

  it("marks phases before, at and after the current phase", () => {
    expect(journeyState(1, 2)).toBe("complete");
    expect(journeyState(2, 2)).toBe("current");
    expect(journeyState(3, 2)).toBe("upcoming");
  });

  it.each([
    ["ROUTING_PENDING", 0, -1],
    ["INFORMATION_REQUIRED", 4, 0],
    ["ON_HOLD", 4, 1],
    ["COORDINATION_REVIEW", 1, 0],
    ["ALLOCATION_REVIEW", 4, 2],
    ["IN_PROGRESS", 4, 4],
  ] as const)("maps %s with a route of %s units to position %s", (status, length, position) => {
    expect(routePosition(status, length)).toBe(position);
  });

  it("labels cancellation and normal completion distinctly", () => {
    expect(lifecycleLabels("CANCELLED").at(-1)).toBe("Closed");
    expect(lifecycleLabels("CLOSED_NOT_PROGRESSED").at(-1)).toBe("Closed");
    expect(lifecycleLabels("COMPLETED").at(-1)).toBe("Customer delivery");
    expect(lifecycleDescription("CANCELLED", 4)).toBe("The request ended before Customer delivery.");
    expect(lifecycleDescription("COMPLETED", 4)).toBe("The response has reached the Customer.");
    expect(lifecycleDescription("COMPLETED", 99)).toBe("Delivery progress is being recorded.");
  });
});
