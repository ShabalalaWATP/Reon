import { act, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { requestDetail, requestSummary, requesterSession, workItem } from "../../test/fixtures";
import { json, mockFetch, renderApp } from "../../test/render";
const EXPECTED_POLL_INTERVAL_MS = 5_000;

afterEach(() => {
  vi.useRealTimers();
});

describe("requester projection refresh", () => {
  it("polls an active register and stops after every request is terminal", async () => {
    vi.useFakeTimers();
    let requestCalls = 0;
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/requests")) {
        requestCalls += 1;
        return json({
          items: [
            {
              ...requestSummary,
              status: requestCalls === 1 ? "IN_PROGRESS" : "COMPLETED",
            },
          ],
        });
      }
      throw new Error(url.pathname);
    });

    renderApp("/requests");
    await vi.waitFor(() => expect(requestCalls).toBe(1), { timeout: 5_000 });
    await act(() => vi.advanceTimersByTimeAsync(EXPECTED_POLL_INTERVAL_MS));
    await vi.waitFor(() => expect(requestCalls).toBe(2), { timeout: 5_000 });
    expect(screen.getByText("Completed history")).toBeInTheDocument();

    await act(() => vi.advanceTimersByTimeAsync(EXPECTED_POLL_INTERVAL_MS * 3));
    expect(requestCalls).toBe(2);
  });

  it("polls an active detail and stops when it becomes terminal", async () => {
    vi.useFakeTimers();
    let detailCalls = 0;
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith(`/requests/${requestDetail.id}`)) {
        detailCalls += 1;
        return json({
          ...requestDetail,
          status: detailCalls === 1 ? "IN_PROGRESS" : "COMPLETED",
        });
      }
      throw new Error(url.pathname);
    });

    renderApp(`/requests/${requestDetail.id}`);
    await vi.waitFor(() => expect(detailCalls).toBe(1), { timeout: 5_000 });
    await act(() => vi.advanceTimersByTimeAsync(EXPECTED_POLL_INTERVAL_MS));
    await vi.waitFor(() => expect(detailCalls).toBe(2), { timeout: 5_000 });
    expect(screen.getByText("Completed")).toBeInTheDocument();

    await act(() => vi.advanceTimersByTimeAsync(EXPECTED_POLL_INTERVAL_MS * 3));
    expect(detailCalls).toBe(2);
  });

  it("polls until the matching clarification task appears, then stops", async () => {
    vi.useFakeTimers();
    const detail = {
      ...requestDetail,
      needsRequesterInput: true,
      status: "INFORMATION_REQUIRED" as const,
    };
    const matchingItem = {
      ...workItem,
      assigneeDisplayName: requesterSession.user.displayName,
      assigneeId: requesterSession.user.id,
      availableActions: ["provide_information"] as const,
      stage: "INFORMATION_REQUIRED" as const,
    };
    let workItemCalls = 0;
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/work-items")) {
        workItemCalls += 1;
        return json({
          items:
            workItemCalls === 1
              ? [{ ...matchingItem, requestId: "another-request" }]
              : [matchingItem],
        });
      }
      if (url.pathname.includes("/requests/")) return json(detail);
      throw new Error(url.pathname);
    });

    renderApp(`/requests/${requestDetail.id}`);
    await vi.waitFor(() => expect(workItemCalls).toBe(1), { timeout: 5_000 });
    expect(screen.getByText("No response task is currently available.")).toBeInTheDocument();
    await act(() => vi.advanceTimersByTimeAsync(EXPECTED_POLL_INTERVAL_MS));
    await vi.waitFor(() => expect(workItemCalls).toBe(2), { timeout: 5_000 });
    expect(screen.getByRole("heading", { name: "Record outcome" })).toBeInTheDocument();

    await act(() => vi.advanceTimersByTimeAsync(EXPECTED_POLL_INTERVAL_MS * 3));
    expect(workItemCalls).toBe(2);
  });
});
