import { describe, expect, it } from "vitest";

import { requestDetail, requestSummary, workItem } from "../../test/fixtures";
import {
  clarificationTaskPollInterval,
  conversationPollInterval,
  requestDetailPollInterval,
  requestListPollInterval,
} from "./requestPolling";

const EXPECTED_POLL_INTERVAL_MS = 5_000;
const EXPECTED_CONVERSATION_INTERVAL_MS = 30_000;

describe("requester projection polling policy", () => {
  it("polls a register only while at least one request remains active", () => {
    expect(
      requestListPollInterval({
        items: [
          { ...requestSummary, status: "COMPLETED" },
          { ...requestSummary, status: "IN_PROGRESS" },
        ],
      }),
    ).toBe(EXPECTED_POLL_INTERVAL_MS);
    expect(
      requestListPollInterval({
        items: [
          { ...requestSummary, status: "COMPLETED" },
          { ...requestSummary, status: "CLOSED_NOT_PROGRESSED" },
          { ...requestSummary, status: "CANCELLED" },
        ],
      }),
    ).toBe(false);
    expect(requestListPollInterval({ items: [] })).toBe(false);
    expect(requestListPollInterval(undefined)).toBe(false);
  });

  it.each(["COMPLETED", "CLOSED_NOT_PROGRESSED", "CANCELLED"] as const)(
    "stops detail polling at terminal status %s",
    (status) => {
      expect(requestDetailPollInterval({ ...requestDetail, status })).toBe(false);
    },
  );

  it("polls an active detail and stops before its first response", () => {
    expect(requestDetailPollInterval(requestDetail)).toBe(EXPECTED_POLL_INTERVAL_MS);
    expect(requestDetailPollInterval(undefined)).toBe(false);
  });

  it.each(["COMPLETED", "CLOSED_NOT_PROGRESSED", "CANCELLED"] as const)(
    "stops conversation polling at terminal status %s",
    (status) => {
      expect(conversationPollInterval(status)).toBe(false);
    },
  );

  it("polls conversations while the request is active or its status is unknown", () => {
    expect(conversationPollInterval("IN_PROGRESS")).toBe(EXPECTED_CONVERSATION_INTERVAL_MS);
    expect(conversationPollInterval(undefined)).toBe(EXPECTED_CONVERSATION_INTERVAL_MS);
  });

  it("polls for clarification until the matching task appears", () => {
    expect(clarificationTaskPollInterval(undefined, requestDetail.id)).toBe(
      EXPECTED_POLL_INTERVAL_MS,
    );
    expect(
      clarificationTaskPollInterval(
        { items: [{ ...workItem, requestId: "another-request" }] },
        requestDetail.id,
      ),
    ).toBe(EXPECTED_POLL_INTERVAL_MS);
    expect(clarificationTaskPollInterval({ items: [workItem] }, requestDetail.id)).toBe(false);
  });
});
