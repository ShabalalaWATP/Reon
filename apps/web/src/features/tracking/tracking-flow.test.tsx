import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import {
  organisationUnit,
  requestDetail,
  requesterSession,
  staffSession,
  trackedRequest,
} from "../../test/fixtures";
import { json, mockFetch, renderApp } from "../../test/render";

describe("route-scoped request tracking", () => {
  it("shows titles, lifecycle graphics and links without loading request content", async () => {
    const paths: string[] = [];
    mockFetch((url) => {
      paths.push(url.pathname);
      if (url.pathname.endsWith("/auth/me")) return json(staffSession);
      if (url.pathname.endsWith("/tracked-requests")) {
        return json({
          items: [
            trackedRequest,
            {
              ...trackedRequest,
              id: "tracked-staffed",
              reference: "ISR-2026-0013",
              title: "Completed route assurance",
              status: "COMPLETED",
              currentOwner: "OSG Team",
              route: [
                organisationUnit("JIOC"),
                organisationUnit("DIGOC"),
                organisationUnit("NCGI_A_OPS"),
                organisationUnit("OSG_TEAM"),
              ].map(({ id, kind, name }) => ({ id, kind, name })),
              awaitingTeamStaffing: false,
            },
            {
              ...trackedRequest,
              id: "tracked-pending",
              reference: "ISR-2026-0014",
              title: "Pending routing request",
              status: "ROUTING_PENDING",
              currentOwner: null,
              route: [],
              awaitingTeamStaffing: false,
            },
          ],
        });
      }
      throw new Error(`Sensitive endpoint requested: ${url.pathname}`);
    });

    const view = renderApp("/tracking");
    expect(await screen.findByRole("heading", { name: "Request tracking" })).toBeInTheDocument();
    expect(screen.getByText("JIOC Routing User")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: trackedRequest.reference })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: trackedRequest.title })).toHaveAttribute(
      "href",
      `/tracking/${trackedRequest.id}`,
    );
    expect(screen.getAllByLabelText(/^Request lifecycle for /)).toHaveLength(3);
    expect(screen.getByText("Ops routing")).toBeInTheDocument();
    expect(screen.getByText("Disseminated")).toBeInTheDocument();
    expect(screen.getAllByText("NCGI-A Ops")).not.toHaveLength(0);
    const routedRow = screen
      .getByRole("heading", { name: trackedRequest.title })
      .closest("article")!;
    expect(within(routedRow).getAllByText("Cedar Team")).not.toHaveLength(0);
    expect(within(routedRow).queryByText("Awaiting team staffing")).not.toBeInTheDocument();
    const staffedRow = screen
      .getByRole("heading", { name: "Completed route assurance" })
      .closest("article")!;
    expect(within(staffedRow).getAllByText("OSG Team")).not.toHaveLength(0);
    expect(within(staffedRow).queryByText("Awaiting team staffing")).not.toBeInTheDocument();
    expect(screen.getByText("Awaiting routing")).toBeInTheDocument();
    expect(screen.getByText("Waiting for the first routing decision.")).toBeInTheDocument();
    expect(screen.queryByText(requestDetail.description)).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Service product" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Approve|Disseminate|Record outcome/ })).not.toBeInTheDocument();
    expect(paths).toEqual(["/api/v1/auth/me", "/api/v1/tracked-requests"]);
    expect(await axe(view.container)).toHaveNoViolations();
  });

  it("opens an authorised historical request as a read-only lifecycle view", async () => {
    const detail = {
      ...trackedRequest,
      requesterDisplayName: requestDetail.requester.displayName,
      description: requestDetail.description,
      questionToAnswer: requestDetail.questionToAnswer,
      desiredOutcome: requestDetail.desiredOutcome,
      backgroundContext: requestDetail.backgroundContext,
      subjectAreaOrLocation: requestDetail.subjectAreaOrLocation,
      coverageStart: requestDetail.coverageStart,
      coverageEnd: requestDetail.coverageEnd,
      customerUrgency: requestDetail.customerUrgency,
      supportedActivityOrDecision: requestDetail.supportedActivityOrDecision,
      requiredByReason: requestDetail.requiredByReason,
      preferredDeliverableType: requestDetail.preferredDeliverableType,
      successCriteria: requestDetail.successCriteria,
      constraintsOrCaveats: requestDetail.constraintsOrCaveats,
      supportingInformation: requestDetail.supportingInformation,
      sensitivity: requestDetail.sensitivity,
      handlingInstructions: requestDetail.handlingInstructions,
    };
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(staffSession);
      if (url.pathname.endsWith(`/tracked-requests/${trackedRequest.id}`)) return json(detail);
      if (url.pathname.endsWith("/tracked-requests")) return json({ items: [trackedRequest] });
      throw new Error(`Unexpected ${url.pathname}`);
    });
    const view = renderApp(`/tracking/${trackedRequest.id}`);

    expect(await screen.findByRole("heading", { name: trackedRequest.title })).toBeInTheDocument();
    expect(screen.getByText(requestDetail.description)).toBeInTheDocument();
    expect(screen.getByText("Read-only lifecycle view")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to tracking" })).toBeInTheDocument();
    expect(screen.getByLabelText(`Request lifecycle for ${trackedRequest.reference}`)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Record outcome|Disseminate|Assign/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Service product" })).not.toBeInTheDocument();
    expect(await axe(view.container)).toHaveNoViolations();
  });

  it("redirects a Customer without fetching tracking metadata", async () => {
    let trackingCalls = 0;
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/tracked-requests")) trackingCalls += 1;
      if (url.pathname.endsWith("/requests")) return json({ items: [] });
      throw new Error(url.pathname);
    });
    renderApp("/tracking");
    expect(await screen.findByRole("heading", { name: "No requests yet" })).toBeInTheDocument();
    expect(trackingCalls).toBe(0);
  });

  it("recovers from an error and renders an empty tracker", async () => {
    let fail = true;
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(staffSession);
      if (url.pathname.endsWith("/tracked-requests")) {
        return fail ? json({ detail: "Unavailable" }, 503) : json({ items: [] });
      }
      throw new Error(url.pathname);
    });
    const user = userEvent.setup();
    renderApp("/tracking");
    expect(await screen.findByRole("heading", { name: "Tracking could not be loaded" })).toBeInTheDocument();
    fail = false;
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: "No requests to track" })).toBeInTheDocument();
  });
});
