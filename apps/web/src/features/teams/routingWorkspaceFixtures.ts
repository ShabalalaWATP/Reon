import type { TrackedRequest } from "../../lib/api/types";
import type { WorkItem } from "../../lib/api/workTypes";
import { trackedRequest } from "../../test/fixtures";

export function tracked(overrides: Partial<TrackedRequest>): TrackedRequest {
  return { ...trackedRequest, id: "tracked-1", ...overrides };
}

export function routingWork(overrides: Partial<WorkItem>): WorkItem {
  return {
    id: "work-1",
    requestId: "request-1",
    requestReference: "REQ-001",
    requestVersion: 1,
    title: "Synthetic routing decision",
    stage: "TRIAGE_REVIEW",
    status: "AVAILABLE",
    assigneeId: null,
    assigneeDisplayName: null,
    deliveryTeam: null,
    availableActions: ["progress"],
    createdAt: "2026-08-09T09:00:00Z",
    updatedAt: "2026-08-09T09:00:00Z",
    ...overrides,
  };
}
