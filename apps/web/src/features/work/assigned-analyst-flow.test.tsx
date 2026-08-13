import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { requestDetail, staffSession, workItem } from "../../test/fixtures";
import { json, mockFetch, renderApp } from "../../test/render";

describe("assigned Analyst production work", () => {
  it("shows the same controls and identifies a non-lead assignment", async () => {
    const analystSession = {
      ...staffSession,
      user: { ...staffSession.user, role: "DELIVERY_SPECIALIST" as const },
    };
    const assigned = {
      ...workItem,
      assignedToCurrentUser: true,
      assignmentRole: "ANALYST" as const,
      assigneeId: "lead-analyst",
      assigneeDisplayName: "Lewis Ferguson",
      availableActions: ["submit" as const, "request_clarification" as const],
      stage: "IN_PROGRESS" as const,
    };
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(analystSession);
      if (url.pathname.endsWith("/work-items")) return json({ items: [assigned] });
      if (url.pathname.includes("/requests/")) return json({
        ...requestDetail,
        contributors: [{ id: analystSession.user.id, displayName: analystSession.user.displayName }],
      });
      throw new Error(url.pathname);
    });

    renderApp("/delivery/my-work");
    expect(await screen.findByText("Assigned to you · Assigned Analyst")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Record outcome" })).toBeInTheDocument();
    expect(screen.getByText("Same working controls as every assigned Analyst")).toBeInTheDocument();
    expect(screen.getByText("Assigned Analysts")).toBeInTheDocument();
  });

  it("marks the accountable Analyst without changing their controls", async () => {
    const analystSession = {
      ...staffSession,
      user: { ...staffSession.user, role: "DELIVERY_SPECIALIST" as const },
    };
    const assigned = {
      ...workItem,
      assignedToCurrentUser: true,
      assignmentRole: "LEAD_ANALYST" as const,
      assigneeId: analystSession.user.id,
      assigneeDisplayName: analystSession.user.displayName,
      availableActions: ["submit" as const],
      stage: "IN_PROGRESS" as const,
    };
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(analystSession);
      if (url.pathname.endsWith("/work-items")) return json({ items: [assigned] });
      if (url.pathname.includes("/requests/")) return json(requestDetail);
      throw new Error(url.pathname);
    });

    renderApp("/delivery/my-work");
    expect(await screen.findByText("Assigned to you · Lead Analyst")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Record outcome" })).toBeInTheDocument();
  });
});
