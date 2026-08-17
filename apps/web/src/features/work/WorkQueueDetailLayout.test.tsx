import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { conversationWorkspace } from "../requests/conversationTestSupport";
import { enabledCapabilities, requestDetail, staffSession, workItem } from "../../test/fixtures";
import { json, mockFeatureFetch, renderApp } from "../../test/render";

function mockAssignedTriageWork({ secondItem = false, unread = false } = {}) {
  const assigned = {
    ...workItem,
    assignedToCurrentUser: true,
    assigneeId: staffSession.user.id,
    stage: "TRIAGE_REVIEW" as const,
  };
  const second = {
    ...assigned,
    id: "second-work-item",
    requestId: "second-request",
    requestReference: "ISR-2026-0013",
    title: "Second synthetic request",
  };
  const requests: string[] = [];
  mockFeatureFetch((url, init) => {
    requests.push(`${init.method ?? "GET"} ${url.pathname}`);
    if (url.pathname.endsWith("/auth/me")) return json(staffSession);
    if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
    if (url.pathname.endsWith("/work-items"))
      return json({ items: secondItem ? [assigned, second] : [assigned] });
    if (url.pathname.endsWith("/read"))
      return json({ conversationId: "conversation", unreadCount: 0 });
    if (url.pathname.endsWith("/conversations"))
      return json(
        unread
          ? {
              ...conversationWorkspace,
              conversations: conversationWorkspace.conversations.map((conversation, index) =>
                index === 1
                  ? {
                      ...conversation,
                      unreadCount: 1,
                      messages: conversation.messages.map((message) => ({
                        ...message,
                        isRead: false,
                      })),
                    }
                  : conversation,
              ),
            }
          : conversationWorkspace,
      );
    if (url.pathname.includes("/related-records")) return json({ items: [] });
    if (url.pathname.includes("/request-links")) return json({ items: [] });
    if (url.pathname.includes("/routing-options")) return json({ items: [] });
    if (url.pathname.endsWith(`/requests/${second.requestId}`))
      return json({
        ...requestDetail,
        id: second.requestId,
        reference: second.requestReference,
        title: second.title,
      });
    if (url.pathname.includes("/requests/")) return json(requestDetail);
    throw new Error(url.pathname);
  });
  return requests;
}

describe("work queue detail layout", () => {
  it("leads with the human decision and reads the submitted request below it", async () => {
    mockAssignedTriageWork();
    renderApp("/triage");
    const decision = await screen.findByText("Human decision");
    const request = await screen.findByRole("heading", { name: "Request details" });
    expect(screen.getByText("Submitted request")).toBeInTheDocument();
    // DOCUMENT_POSITION_FOLLOWING: the request heading comes after the decision.
    expect(decision.compareDocumentPosition(request) & Node.DOCUMENT_POSITION_FOLLOWING).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
  });

  it("does not load correspondence until it opens and closes it on request change", async () => {
    const requests = mockAssignedTriageWork({ secondItem: true, unread: true });
    const user = userEvent.setup();
    renderApp("/triage");
    const summary = await screen.findByText(
      "Request information from the Customer or another team",
    );
    const disclosure = summary.closest("details");
    expect(disclosure).not.toBeNull();
    // jsdom keeps closed <details> content in the DOM, so the open attribute is
    // the faithful signal of what a browser shows.
    expect(disclosure).not.toHaveAttribute("open");
    expect(screen.queryByRole("heading", { name: "Conversations" })).not.toBeInTheDocument();
    expect(requests.some((request) => request.includes("/conversations"))).toBe(false);
    expect(requests.some((request) => request.endsWith("/read"))).toBe(false);

    await user.click(summary);
    expect(disclosure).toHaveAttribute("open");
    expect(await screen.findByRole("heading", { name: "Conversations" })).toBeInTheDocument();
    await waitFor(() => expect(requests.some((request) => request.endsWith("/read"))).toBe(true));

    await user.click(screen.getByRole("button", { name: /Second synthetic request/u }));
    expect(await screen.findByRole("heading", { name: "Second synthetic request" })).toBeVisible();
    const nextSummary = await screen.findByText(
      "Request information from the Customer or another team",
    );
    expect(nextSummary.closest("details")).not.toHaveAttribute("open");
    expect(screen.queryByRole("heading", { name: "Conversations" })).not.toBeInTheDocument();
    expect(requests.some((request) => request.includes("/second-request/conversations"))).toBe(
      false,
    );
  });
});
