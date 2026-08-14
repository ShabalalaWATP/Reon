import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import {
  enabledCapabilities,
  requestDetail,
  requesterSession,
  workItem,
} from "../../test/fixtures";
import { json, mockFeatureFetch, renderApp } from "../../test/render";

describe("requester experience", () => {
  it("lets a requester provide information through their named work item", async () => {
    const infoRequest = {
      ...requestDetail,
      status: "INFORMATION_REQUIRED" as const,
      needsRequesterInput: true,
      workflowError: "sync delayed",
      events: [],
    };
    const item = {
      ...workItem,
      stage: "INFORMATION_REQUIRED" as const,
      assigneeId: requesterSession.user.id,
      assigneeDisplayName: requesterSession.user.displayName,
      availableActions: ["provide_information", "withdraw"] as const,
    };
    let completedBody: unknown;
    mockFeatureFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/work-items")) return json({ items: [item] });
      if (url.pathname.endsWith("/complete")) {
        completedBody = JSON.parse(String(init.body));
        return json(requestDetail);
      }
      if (url.pathname.includes("/requests/")) return json(infoRequest);
      if (url.pathname.endsWith("/requests")) return json({ items: [] });
      throw new Error(url.pathname);
    });
    const user = userEvent.setup();
    renderApp(`/requests/${requestDetail.id}`);
    expect(await screen.findByRole("heading", { name: "Record outcome" })).toBeInTheDocument();
    expect(
      screen.getByText("Progress is temporarily delayed. Staff have been notified."),
    ).toBeInTheDocument();
    expect(screen.getByText("No activity has been recorded yet.")).toBeInTheDocument();
    await user.type(
      screen.getByLabelText("Additional information"),
      "The meeting has moved to 20 September.",
    );
    await user.click(screen.getByRole("button", { name: "Provide information" }));
    await waitFor(() =>
      expect(completedBody).toEqual({
        action: "provide_information",
        information: "The meeting has moved to 20 September.",
      }),
    );
  });

  it("shows the stored production conversation and returns information to the Analyst", async () => {
    const clarification = {
      id: "thread-1",
      sequence: 1,
      question: "Which fictional region should be prioritised?",
      reason: "The product needs a bounded scope.",
      responseDeadline: "2026-09-10",
      status: "OPEN" as const,
      version: 2,
      assignedSpecialist: { id: "analyst-1", displayName: "Denis Law" },
      messages: [
        {
          id: "message-1",
          kind: "REQUEST" as const,
          body: "Which fictional region should be prioritised?",
          actorDisplayName: "Denis Law",
          createdAt: "2026-08-06T11:00:00Z",
        },
      ],
      createdAt: "2026-08-06T11:00:00Z",
      closedAt: null,
    };
    const detail = {
      ...requestDetail,
      status: "CUSTOMER_INFORMATION_REQUIRED" as const,
      needsRequesterInput: true,
      clarifications: [clarification],
    };
    const item = {
      ...workItem,
      stage: "CUSTOMER_INFORMATION_REQUIRED" as const,
      assigneeId: requesterSession.user.id,
      assigneeDisplayName: requesterSession.user.displayName,
      availableActions: ["provide_clarification", "withdraw"] as const,
    };
    let completedBody: unknown;
    mockFeatureFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/work-items")) return json({ items: [item] });
      if (url.pathname.endsWith("/complete")) {
        completedBody = JSON.parse(String(init.body));
        return json(requestDetail);
      }
      if (url.pathname.includes("/requests/")) return json(detail);
      if (url.pathname.endsWith("/requests")) return json({ items: [] });
      throw new Error(url.pathname);
    });
    const user = userEvent.setup();
    const view = renderApp(`/requests/${requestDetail.id}`);
    expect(
      await screen.findByRole("heading", { name: "Additional information" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: clarification.question })).toBeInTheDocument();
    expect(screen.getByText(/The product needs a bounded scope/)).toBeInTheDocument();
    await user.type(
      await screen.findByLabelText("Information for the Analyst"),
      "Prioritise the fictional northern region.",
    );
    await user.click(screen.getByRole("button", { name: "Send information to Analyst" }));
    await waitFor(() =>
      expect(completedBody).toEqual({
        action: "provide_clarification",
        threadId: "thread-1",
        expectedVersion: 2,
        information: "Prioritise the fictional northern region.",
      }),
    );
    expect(await axe(view.container)).toHaveNoViolations();
  });

  it("handles unavailable details and feedback errors", async () => {
    let failFeedback = false;
    const complete = {
      ...requestDetail,
      status: "COMPLETED" as const,
      deliverable: { id: "d", title: "Result", text: "Text", releasedAt: requestDetail.updatedAt },
    };
    mockFeatureFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/missing")) return json({ detail: "Not found" }, 404);
      if (url.pathname.endsWith("/feedback"))
        return failFeedback ? json({ detail: "Feedback already submitted" }, 409) : json({});
      return json(complete);
    });
    renderApp("/requests/missing");
    expect(
      await screen.findByRole("heading", { name: "Request not available" }),
    ).toBeInTheDocument();
    failFeedback = true;
  });
});
