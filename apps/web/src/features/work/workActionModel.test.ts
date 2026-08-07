import { describe, expect, it } from "vitest";

import {
  actionRequiresDestination,
  buildWorkAction,
  workActionSchema,
  type WorkActionValues,
} from "./workActionModel";

const cases: Array<[WorkActionValues, unknown]> = [
  [{ action: "request_information", reason: "Need a clearer deadline." }, { action: "request_information", reason: "Need a clearer deadline." }],
  [{ action: "progress", category: "Advisory", destinationUnitId: "command-id", priority: "HIGH" }, { action: "progress", category: "Advisory", destinationUnitId: "command-id", priority: "HIGH" }],
  [{ action: "close", reason: "Outside scope." }, { action: "close", reason: "Outside scope." }],
  [{ action: "provide_information", information: "The meeting is on Friday." }, { action: "provide_information", information: "The meeting is on Friday." }],
  [{ action: "withdraw", reason: "No longer required." }, { action: "withdraw", reason: "No longer required." }],
  [{ action: "send_to_allocation", destinationUnitId: "ops-id", note: "Please prioritise." }, { action: "send_to_allocation", destinationUnitId: "ops-id", note: "Please prioritise." }],
  [{ action: "return_to_triage", reason: "Category needs review." }, { action: "return_to_triage", reason: "Category needs review." }],
  [{ action: "hold", reason: "Awaiting decision." }, { action: "hold", reason: "Awaiting decision." }],
  [{ action: "resume", note: "Decision received." }, { action: "resume", note: "Decision received." }],
  [{ action: "allocate", destinationUnitId: "team-id", requiredCapabilities: "Writing\nData review\n" }, { action: "allocate", destinationUnitId: "team-id", requiredCapabilities: ["Writing", "Data review"] }],
  [{ action: "return_to_coordination", reason: "Needs service decision." }, { action: "return_to_coordination", reason: "Needs service decision." }],
  [{ action: "assign", specialistId: "specialist-id" }, { action: "assign", specialistId: "specialist-id" }],
  [{ action: "return_for_reallocation", reason: "Capability unavailable." }, { action: "return_for_reallocation", reason: "Capability unavailable." }],
  [{ action: "submit", deliverableTitle: "Readiness note", deliverableText: "Complete result." }, { action: "submit", deliverableTitle: "Readiness note", deliverableText: "Complete result." }],
  [{ action: "request_clarification", question: "Which region?", reason: "Needed for scope.", responseDeadline: "2026-09-10" }, { action: "request_clarification", question: "Which region?", reason: "Needed for scope.", responseDeadline: "2026-09-10" }],
  [{ action: "provide_clarification", threadId: "thread-1", expectedVersion: 2, information: "The northern region." }, { action: "provide_clarification", threadId: "thread-1", expectedVersion: 2, information: "The northern region." }],
  [{ action: "approve" }, { action: "approve" }],
  [{ action: "changes_required", reason: "Clarify the conclusion." }, { action: "changes_required", reason: "Clarify the conclusion." }],
  [{ action: "release", recipients: "Service lead\nRequesting area" }, { action: "release", recipients: ["Service lead", "Requesting area"] }],
];

describe("work action model", () => {
  it.each(cases)("builds the exact %s payload", (values, expected) => {
    expect(buildWorkAction(values)).toEqual(expected);
  });

  it.each([
    "request_information", "close", "withdraw", "return_to_triage", "hold",
    "return_to_coordination", "return_for_reallocation", "changes_required",
  ] as const)("requires a reason for %s", (action) => {
    expect(workActionSchema.safeParse({ action, reason: " " }).success).toBe(false);
  });

  it.each([
    [{ action: "progress" }, 3],
    [{ action: "send_to_allocation" }, 2],
    [{ action: "allocate" }, 2],
    [{ action: "assign" }, 1],
    [{ action: "submit" }, 2],
    [{ action: "provide_information" }, 1],
    [{ action: "request_clarification" }, 3],
    [{ action: "provide_clarification" }, 3],
    [{ action: "release" }, 1],
  ])("requires fields for structured actions", (value, issueCount) => {
    const result = workActionSchema.safeParse(value);
    expect(result.success).toBe(false);
    if (!result.success) expect(result.error.issues).toHaveLength(issueCount);
  });

  it("accepts outcomes without required fields", () => {
    expect(workActionSchema.safeParse({ action: "approve" }).success).toBe(true);
    expect(workActionSchema.safeParse({ action: "resume" }).success).toBe(false);
  });

  it("identifies only actions that require a destination", () => {
    expect(actionRequiresDestination("progress")).toBe(true);
    expect(actionRequiresDestination("send_to_allocation")).toBe(true);
    expect(actionRequiresDestination("allocate")).toBe(true);
    expect(actionRequiresDestination("approve")).toBe(false);
    expect(actionRequiresDestination()).toBe(false);
  });
});
