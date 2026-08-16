import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { conversationWorkspace } from "../requests/conversationTestSupport";
import { enabledCapabilities, requestDetail, staffSession, workItem } from "../../test/fixtures";
import { json, mockFeatureFetch, renderApp } from "../../test/render";

function mockAssignedTriageWork() {
  const assigned = {
    ...workItem,
    assignedToCurrentUser: true,
    assigneeId: staffSession.user.id,
    stage: "TRIAGE_REVIEW" as const,
  };
  mockFeatureFetch((url) => {
    if (url.pathname.endsWith("/auth/me")) return json(staffSession);
    if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
    if (url.pathname.endsWith("/work-items")) return json({ items: [assigned] });
    if (url.pathname.endsWith("/conversations")) return json(conversationWorkspace);
    if (url.pathname.includes("/related-records")) return json({ items: [] });
    if (url.pathname.includes("/request-links")) return json({ items: [] });
    if (url.pathname.includes("/routing-options")) return json({ items: [] });
    if (url.pathname.includes("/requests/")) return json(requestDetail);
    throw new Error(url.pathname);
  });
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

  it("keeps correspondence collapsed until a routing user opens it", async () => {
    mockAssignedTriageWork();
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

    await user.click(summary);
    expect(disclosure).toHaveAttribute("open");
    expect(screen.getByRole("heading", { name: "Conversations" })).toBeInTheDocument();
  });
});
