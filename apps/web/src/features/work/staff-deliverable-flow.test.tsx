import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import type { UserRole, WorkAction, WorkStage } from "../../lib/api/types";
import { requestDetail, staffSession, workItem } from "../../test/fixtures";
import { json, mockFetch, renderApp } from "../../test/render";
import { StaffDeliverableSection } from "./StaffDeliverableSection";

const reviewCases: Array<{
  action: WorkAction["action"];
  context: string;
  path: string;
  role: UserRole;
  stage: WorkStage;
}> = [
  {
    action: "approve",
    context: "Submitted service product",
    path: "/delivery/team",
    role: "DELIVERY_TEAM_LEAD",
    stage: "LEAD_REVIEW",
  },
  {
    action: "approve",
    context: "Service product for QC review",
    path: "/quality-release",
    role: "QUALITY_RELEASE",
    stage: "QUALITY_REVIEW",
  },
  {
    action: "submit",
    context: "Latest submitted version",
    path: "/delivery/my-work",
    role: "DELIVERY_SPECIALIST",
    stage: "REWORK_REQUIRED",
  },
  {
    action: "release",
    context: "Approved service product",
    path: "/quality-release",
    role: "QUALITY_RELEASE",
    stage: "READY_FOR_RELEASE",
  },
];

describe("staff deliverable review", () => {
  it.each(reviewCases)(
    "shows the submitted work before $stage controls",
    async ({ action, context, path, role, stage }) => {
      const session = {
        ...staffSession,
        user: { ...staffSession.user, role },
      };
      const item = {
        ...workItem,
        assigneeDisplayName: session.user.displayName,
        assigneeId: session.user.id,
        availableActions: [action],
        stage,
      };
      const detail = {
        ...requestDetail,
        deliverable: {
          id: "deliverable",
          releasedAt: null,
          text: "The submitted evidence and recommendations.",
          title: "Service readiness assessment",
        },
        status: stage,
      };
      mockFetch((url) => {
        if (url.pathname.endsWith("/auth/me")) return json(session);
        if (url.pathname.endsWith("/work-items")) return json({ items: [item] });
        if (url.pathname.includes("/requests/")) return json(detail);
        throw new Error(url.pathname);
      });

      const view = renderApp(path);
      const actionHeading = await screen.findByRole("heading", {
        name: "Record outcome",
      });
      const deliverableHeading = screen.getByRole("heading", {
        name: "Service product",
      });
      expect(screen.getByText(context)).toBeInTheDocument();
      expect(screen.getByText("Service readiness assessment")).toBeInTheDocument();
      expect(screen.getByText("The submitted evidence and recommendations.")).toBeInTheDocument();
      expect(screen.getByText("Not yet disseminated")).toBeInTheDocument();
      expect(
        deliverableHeading.compareDocumentPosition(actionHeading) &
          Node.DOCUMENT_POSITION_FOLLOWING,
      ).toBeTruthy();
      expect(await axe(view.container)).toHaveNoViolations();
    },
  );

  it("shows loading and then an explicit empty review state", async () => {
    const session = {
      ...staffSession,
      user: { ...staffSession.user, role: "DELIVERY_TEAM_LEAD" as const },
    };
    const item = {
      ...workItem,
      assigneeDisplayName: session.user.displayName,
      assigneeId: session.user.id,
      availableActions: ["approve"] as const,
      stage: "LEAD_REVIEW" as const,
    };
    let resolveDetail!: (response: Response) => void;
    const detailResponse = new Promise<Response>((resolve) => {
      resolveDetail = resolve;
    });
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(session);
      if (url.pathname.endsWith("/work-items")) return json({ items: [item] });
      if (url.pathname.includes("/requests/")) return detailResponse;
      throw new Error(url.pathname);
    });

    renderApp("/delivery/team");
    expect(await screen.findByText("Loading submitted service product…")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Record outcome" })).not.toBeInTheDocument();
    resolveDetail(json({ ...requestDetail, status: "LEAD_REVIEW" }));
    expect(
      await screen.findByText("No submitted service product is available for this stage."),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Record outcome" })).toBeInTheDocument();
  });

  it("handles hidden, failed and released presentation states", () => {
    const { rerender } = render(<StaffDeliverableSection stage="IN_PROGRESS" state="ready" />);
    expect(screen.queryByRole("heading", { name: "Service product" })).not.toBeInTheDocument();

    rerender(<StaffDeliverableSection stage="QUALITY_REVIEW" state="error" />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Submitted service product could not be loaded.",
    );

    rerender(
      <StaffDeliverableSection
        deliverable={{
          id: "released",
          releasedAt: "2026-08-06T11:00:00Z",
          text: "Released text",
          title: "Released result",
        }}
        stage="READY_FOR_RELEASE"
        state="ready"
      />,
    );
    expect(screen.getByText(/Disseminated 06 Aug 2026/)).toBeInTheDocument();
    expect(screen.getByText("Approved service product")).toBeInTheDocument();
  });
});
