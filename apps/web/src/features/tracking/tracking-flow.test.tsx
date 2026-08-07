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

describe("metadata-only request tracking", () => {
  it("shows routing metadata without request or product content", async () => {
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
    expect(screen.getByRole("heading", { name: trackedRequest.reference })).toBeInTheDocument();
    expect(screen.getByText("Ops routing")).toBeInTheDocument();
    expect(screen.getByText("Disseminated")).toBeInTheDocument();
    expect(screen.getAllByText("NCGI-A Ops")).not.toHaveLength(0);
    const routedRow = screen
      .getByRole("heading", { name: trackedRequest.reference })
      .closest("article")!;
    expect(within(routedRow).getAllByText("Cedar Team")).not.toHaveLength(0);
    expect(within(routedRow).queryByText("Awaiting team staffing")).not.toBeInTheDocument();
    const staffedRow = screen
      .getByRole("heading", { name: "ISR-2026-0013" })
      .closest("article")!;
    expect(within(staffedRow).getAllByText("OSG Team")).not.toHaveLength(0);
    expect(within(staffedRow).queryByText("Awaiting team staffing")).not.toBeInTheDocument();
    expect(screen.getByText("Awaiting routing")).toBeInTheDocument();
    expect(screen.getByText("Route pending")).toBeInTheDocument();
    expect(screen.queryByText(requestDetail.title)).not.toBeInTheDocument();
    expect(screen.queryByText(requestDetail.description)).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Service product" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Approve|Disseminate|Record outcome/ })).not.toBeInTheDocument();
    expect(paths).toEqual(["/api/v1/auth/me", "/api/v1/tracked-requests"]);
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
