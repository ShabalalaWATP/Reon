import { describe, expect, it } from "vitest";

import { requestDetail, workItem } from "../../test/fixtures";
import { json, mockFetch } from "../../test/render";
import { api } from "./client";
import { parseRequestDetail, parseWorkItem } from "./payloadSchemas";

describe("API payload contracts", () => {
  it("returns a compatible request and work item unchanged", () => {
    expect(parseRequestDetail(requestDetail)).toEqual(requestDetail);
    expect(parseWorkItem(workItem)).toEqual(workItem);
  });

  it.each([
    ["a missing urgency", { ...requestDetail, customerUrgency: undefined }],
    ["an unknown sensitivity", { ...requestDetail, sensitivity: "SECRET" }],
    ["a contributor list that is not an array", { ...requestDetail, contributors: null }],
    ["an incomplete clarification thread", { ...requestDetail, clarifications: [{ id: "one" }] }],
    ["a missing deliverable field", { ...requestDetail, deliverable: { id: "one" } }],
  ])("rejects a request payload with %s", (_label, payload) => {
    expect(() => parseRequestDetail(payload)).toThrow(/incompatible/);
  });

  it.each([
    ["an unknown stage", { ...workItem, stage: "SYNTHETIC_STAGE" }],
    ["an unknown available action", { ...workItem, availableActions: ["teleport"] }],
    ["a missing request reference", { ...workItem, requestReference: undefined }],
  ])("rejects a work item payload with %s", (_label, payload) => {
    expect(() => parseWorkItem(payload)).toThrow(/incompatible/);
  });

  it("names the payload that failed its contract", () => {
    expect(() => parseWorkItem({})).toThrow("The server returned an incompatible work item.");
  });

  it("fails a request detail call instead of handing a component the wrong shape", async () => {
    mockFetch(() => json({ ...requestDetail, customerUrgency: 7 }));

    await expect(api.request("request-1")).rejects.toThrow(
      "The server returned an incompatible request.",
    );
  });

  it("leaves unvalidated calls returning the raw body", async () => {
    mockFetch(() => json({ items: [] }));

    await expect(api.requests()).resolves.toEqual({ items: [] });
  });
});
