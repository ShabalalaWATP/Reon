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
      if (url.pathname.endsWith("/organisation/units")) return json({ items: [] });
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
              currentOwner: "SSG Team",
              route: [
                organisationUnit("CRIOC"),
                organisationUnit("JOCK"),
                organisationUnit("ACSA_B_OPS"),
                organisationUnit("SSG_TEAM"),
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
    expect(screen.getByText("CRIOC Routing User")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: trackedRequest.reference })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: trackedRequest.title })).toHaveAttribute(
      "href",
      `/tracking/${trackedRequest.id}`,
    );
    expect(screen.getAllByLabelText(/^Request lifecycle for /)).toHaveLength(3);
    expect(screen.getAllByText("Ops routing")).not.toHaveLength(0);
    expect(screen.getAllByText("Disseminated")).not.toHaveLength(0);
    expect(screen.getAllByText("ACSA-B Ops")).not.toHaveLength(0);
    const routedRow = screen
      .getByRole("heading", { name: trackedRequest.title })
      .closest("article")!;
    expect(within(routedRow).getAllByText("Cedar Team")).not.toHaveLength(0);
    expect(within(routedRow).queryByText("Awaiting team staffing")).not.toBeInTheDocument();
    const staffedRow = screen
      .getByRole("heading", { name: "Completed route assurance" })
      .closest("article")!;
    expect(within(staffedRow).getAllByText("SSG Team")).not.toHaveLength(0);
    expect(within(staffedRow).queryByText("Awaiting team staffing")).not.toBeInTheDocument();
    expect(screen.getByText("Awaiting routing")).toBeInTheDocument();
    expect(screen.getByText("Waiting for the first routing decision.")).toBeInTheDocument();
    expect(screen.queryByText(requestDetail.description)).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Service product" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Approve|Disseminate|Record outcome/ })).not.toBeInTheDocument();
    expect(paths[0]).toBe("/api/v1/auth/me");
    expect(new Set(paths.slice(1))).toEqual(new Set([
      "/api/v1/organisation/units",
      "/api/v1/tracked-requests",
    ]));
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
      events: [{
        id: "event-1",
        type: "ROUTED",
        message: "Request routed to ACSA-B Ops",
        actorDisplayName: "CRIOC Routing User",
        priorStatus: "COORDINATION_REVIEW",
        nextStatus: "ALLOCATION_REVIEW",
        createdAt: "2026-08-06T10:00:00Z",
      }],
      eventsNextCursor: null,
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
    expect(screen.getByText("Request routed to ACSA-B Ops")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Record outcome|Disseminate|Assign/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Service product" })).not.toBeInTheDocument();
    expect(await axe(view.container)).toHaveNoViolations();
  });

  it("records route-scoped questions and return requests without claiming work", async () => {
    const commands: unknown[] = [];
    let rejectMessage = false;
    let rejectReturn = false;
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
      events: [],
      eventsNextCursor: null,
    };
    mockFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(staffSession);
      if (url.pathname.endsWith(`/tracked-requests/${trackedRequest.id}`)) return json(detail);
      if (init.method === "POST") {
        if (rejectMessage && url.pathname.endsWith("/coordination")) {
          return json({ detail: "The message could not be recorded." }, 409);
        }
        if (rejectReturn && url.pathname.endsWith("/return-requests")) {
          return json({ detail: "The current owner could not be contacted." }, 409);
        }
        commands.push(JSON.parse(String(init.body)));
        return json({ event: { id: `event-${commands.length}` } });
      }
      throw new Error(`Unexpected ${url.pathname}`);
    });
    const user = userEvent.setup();
    renderApp(`/tracking/${trackedRequest.id}`);
    await screen.findByRole("heading", { name: "Questions and return requests" });

    await user.selectOptions(screen.getByLabelText("Send to"), "CUSTOMER");
    await user.type(screen.getByLabelText("Message"), "Can the Customer confirm the priority?");
    await user.click(screen.getByRole("button", { name: "Send message" }));
    await user.type(screen.getByLabelText("Reason"), "CRIOC needs to reconsider the routing decision.");
    await user.click(screen.getByRole("button", { name: "Request return" }));

    expect(commands).toEqual([
      { audience: "CUSTOMER", body: "Can the Customer confirm the priority?" },
      {
        targetUnitId: trackedRequest.route[0].id,
        reason: "CRIOC needs to reconsider the routing decision.",
      },
    ]);

    rejectReturn = true;
    await user.type(screen.getByLabelText("Reason"), "This later return request should fail safely.");
    await user.click(screen.getByRole("button", { name: "Request return" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The current owner could not be contacted.",
    );
    rejectMessage = true;
    await user.type(screen.getByLabelText("Message"), "This later message should fail safely.");
    await user.click(screen.getByRole("button", { name: "Send message" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The message could not be recorded.",
    );
  });

  it("filters monitored work independently from the action queue", async () => {
    const trackingQueries: URLSearchParams[] = [];
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(staffSession);
      if (url.pathname.endsWith("/organisation/units")) {
        return json({ items: [organisationUnit("ACSA_B_OPS")] });
      }
      if (url.pathname.endsWith("/tracked-requests")) {
        trackingQueries.push(url.searchParams);
        return json({ items: [trackedRequest] });
      }
      throw new Error(url.pathname);
    });
    const user = userEvent.setup();
    renderApp("/tracking");
    await screen.findByRole("heading", { name: "Request tracking" });
    await user.click(screen.getByText("Filter monitored requests"));
    await user.type(screen.getByLabelText("Reference or title"), "readiness");
    await user.selectOptions(screen.getByLabelText("Status"), "ALLOCATION_REVIEW");
    await user.type(screen.getByLabelText("Current owner"), "Cedar");
    await user.selectOptions(screen.getByLabelText("Route destination"), organisationUnit("ACSA_B_OPS").id);
    await user.selectOptions(screen.getByLabelText("Open for at least"), "7");
    await user.click(screen.getByRole("button", { name: "Apply filters" }));
    await screen.findByText("Filter monitored requests · Active");

    const applied = trackingQueries.at(-1)!;
    expect(Object.fromEntries(applied)).toEqual({
      search: "readiness",
      status: "ALLOCATION_REVIEW",
      currentOwner: "Cedar",
      routeUnitId: organisationUnit("ACSA_B_OPS").id,
      minimumAgeDays: "7",
    });
    await user.click(screen.getByRole("button", { name: "Clear" }));
    expect(screen.getByLabelText("Reference or title")).toHaveValue("");
  });

  it("pages through older immutable ticket history", async () => {
    const detail = {
      ...trackedRequest,
      requesterDisplayName: requestDetail.requester.displayName,
      ...Object.fromEntries([
        "description", "questionToAnswer", "desiredOutcome", "backgroundContext",
        "subjectAreaOrLocation", "coverageStart", "coverageEnd", "customerUrgency",
        "supportedActivityOrDecision", "requiredByReason", "preferredDeliverableType",
        "successCriteria", "constraintsOrCaveats", "supportingInformation",
        "sensitivity", "handlingInstructions",
      ].map((key) => [key, requestDetail[key as keyof typeof requestDetail]])),
      events: [],
      eventsNextCursor: "older",
    };
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(staffSession);
      if (url.pathname.endsWith(`/tracked-requests/${trackedRequest.id}`)) {
        if (url.searchParams.get("eventCursor") === "older") {
          return json({ ...detail, events: [{ id: "old", type: "ROUTED", message: "Earlier routing decision", actorDisplayName: null, priorStatus: null, nextStatus: null, createdAt: "2026-08-01T10:00:00Z" }], eventsNextCursor: null });
        }
        return json(detail);
      }
      throw new Error(url.pathname);
    });
    const user = userEvent.setup();
    renderApp(`/tracking/${trackedRequest.id}`);
    await user.click(await screen.findByRole("button", { name: "Load more" }));
    expect(await screen.findByText("Earlier routing decision")).toBeInTheDocument();
  });

  it("reports an unavailable older history page without losing the request", async () => {
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
      events: [],
      eventsNextCursor: "older",
    };
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(staffSession);
      if (url.searchParams.has("eventCursor")) return json({ detail: "Unavailable" }, 503);
      if (url.pathname.endsWith(`/tracked-requests/${trackedRequest.id}`)) return json(detail);
      throw new Error(url.pathname);
    });
    const user = userEvent.setup();
    renderApp(`/tracking/${trackedRequest.id}`);
    await user.click(await screen.findByRole("button", { name: "Load more" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Older ticket history could not be loaded.");
    expect(screen.getByRole("heading", { name: trackedRequest.title })).toBeInTheDocument();
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
