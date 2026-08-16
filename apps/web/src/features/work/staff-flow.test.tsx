import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { WorkItem } from "../../lib/api/types";
import {
  organisationChildren,
  organisationUnit,
  requestDetail,
  staffSession,
  workItem,
} from "../../test/fixtures";
import { json, mockFetch, renderApp } from "../../test/render";

describe("staff work queue", () => {
  it("opens the exact request from an action link without falling back", async () => {
    const requested: string[] = [];
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(staffSession);
      if (url.pathname.endsWith("/work-items")) {
        requested.push(url.searchParams.get("requestId") ?? "");
        return json({
          items: url.searchParams.get("requestId") === workItem.requestId ? [workItem] : [],
        });
      }
      throw new Error(`Unexpected ${url.pathname}`);
    });

    const exact = renderApp(`/triage?requestId=${workItem.requestId}`);
    expect(await screen.findAllByText(workItem.requestReference)).toHaveLength(2);
    expect(requested).toEqual([workItem.requestId]);
    exact.unmount();

    renderApp("/triage?requestId=aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa");
    expect(
      await screen.findByRole("heading", { name: "This action is no longer available" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open JIOC routing queue" })).toHaveAttribute(
      "href",
      "/triage",
    );
  });

  it("claims work and records a stage-specific human outcome", async () => {
    let item = workItem;
    let completeBody: unknown;
    let requestDetailCalls = 0;
    mockFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(staffSession);
      if (url.pathname.endsWith("/work-items")) return json({ items: item ? [item] : [] });
      if (url.pathname.endsWith("/claim")) {
        item = {
          ...item,
          assigneeId: staffSession.user.id,
          assigneeDisplayName: staffSession.user.displayName,
          status: "CLAIMED",
        };
        return json(item);
      }
      if (url.pathname.endsWith("/routing-options")) {
        return json({ items: organisationChildren("CRIOC") });
      }
      if (url.pathname.endsWith("/complete")) {
        completeBody = JSON.parse(String(init.body));
        item = undefined as never;
        return json(requestDetail);
      }
      if (url.pathname.endsWith(`/requests/${requestDetail.id}`)) {
        requestDetailCalls += 1;
        return json(requestDetail);
      }
      throw new Error(`Unexpected ${url.pathname} ${init.method ?? "GET"}`);
    });
    const user = userEvent.setup();
    renderApp("/triage");
    expect(await screen.findByRole("heading", { name: "JIOC routing queue" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Claim work item" })).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Claim to view request context" }),
    ).toBeInTheDocument();
    expect(requestDetailCalls).toBe(0);
    await user.click(screen.getByRole("button", { name: "Claim work item" }));
    expect(await screen.findByRole("heading", { name: "Record outcome" })).toBeInTheDocument();
    await waitFor(() => expect(requestDetailCalls).toBe(1));
    await user.selectOptions(screen.getByLabelText("Outcome"), "progress");
    await screen.findByRole("option", { name: /JOCK/ });
    await user.selectOptions(
      screen.getByLabelText("Destination unit"),
      organisationUnit("JOCK").id,
    );
    await user.click(screen.getByRole("button", { name: "Route to command" }));
    expect(await screen.findByText("Choose a priority.")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText(/Priority/), "HIGH");
    await user.click(screen.getByRole("button", { name: "Route to command" }));
    await waitFor(() =>
      expect(completeBody).toEqual({
        action: "progress",
        destinationUnitId: "unit-jock",
        priority: "HIGH",
      }),
    );
    expect(await screen.findByRole("heading", { name: "No items waiting" })).toBeInTheDocument();
    expect(requestDetailCalls).toBe(1);
  });

  it("loads eligible specialists only for assignment and submits the selected identifier", async () => {
    const teamLeadSession = {
      ...staffSession,
      user: {
        ...staffSession.user,
        role: "DELIVERY_TEAM_LEAD" as const,
        scope: "DELIVERY_TEAM_A",
      },
    };
    let item: WorkItem | undefined = {
      ...workItem,
      assigneeDisplayName: teamLeadSession.user.displayName,
      assigneeId: teamLeadSession.user.id,
      availableActions: ["return_for_reallocation", "assign"],
      deliveryTeam: "DELIVERY_TEAM_A",
      stage: "DELIVERY_PLANNING",
    };
    let completeBody: unknown;
    let eligibleCalls = 0;
    let resolveSpecialists!: (response: Response) => void;
    const specialistsResponse = new Promise<Response>((resolve) => {
      resolveSpecialists = resolve;
    });
    mockFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(teamLeadSession);
      if (url.pathname.endsWith("/eligible-specialists")) {
        eligibleCalls += 1;
        return specialistsResponse;
      }
      if (url.pathname.endsWith("/work-items")) {
        return json({ items: item ? [item] : [] });
      }
      if (url.pathname.endsWith("/complete")) {
        completeBody = JSON.parse(String(init.body));
        item = undefined;
        return json(requestDetail);
      }
      if (url.pathname.includes("/requests/")) return json(requestDetail);
      throw new Error(`Unexpected ${url.pathname} ${init.method ?? "GET"}`);
    });

    const user = userEvent.setup();
    renderApp("/delivery/team");
    const outcome = await screen.findByLabelText("Outcome");
    expect(eligibleCalls).toBe(0);

    await user.selectOptions(outcome, "assign");
    expect(await screen.findByRole("status")).toHaveTextContent("Loading eligible Analysts…");
    expect(eligibleCalls).toBe(1);
    resolveSpecialists(
      json({
        items: [
          { id: "specialist-a", displayName: "Aisha Rahman" },
          { id: "specialist-b", displayName: "Euan Fraser" },
        ],
      }),
    );

    const specialistSelect = await screen.findByLabelText("Lead Analyst");
    await waitFor(() => expect(specialistSelect).toBeEnabled());
    expect(
      within(specialistSelect).getByRole("option", { name: "Euan Fraser" }),
    ).toBeInTheDocument();
    await user.selectOptions(specialistSelect, "specialist-b");
    await user.type(
      screen.getByLabelText(/^Assignment reason/),
      "Euan will lead this delivery request.",
    );
    await user.click(screen.getByRole("button", { name: "Assign Analysts" }));

    await waitFor(() =>
      expect(completeBody).toEqual({
        action: "assign",
        contributorIds: [],
        reason: "Euan will lead this delivery request.",
        specialistId: "specialist-b",
      }),
    );
    expect(await screen.findByRole("heading", { name: "No items waiting" })).toBeInTheDocument();
  });

  it("recovers specialist options from an error and reports an empty team", async () => {
    const teamLeadSession = {
      ...staffSession,
      user: {
        ...staffSession.user,
        role: "DELIVERY_TEAM_LEAD" as const,
        scope: "DELIVERY_TEAM_A",
      },
    };
    const planningItem: WorkItem = {
      ...workItem,
      assigneeDisplayName: teamLeadSession.user.displayName,
      assigneeId: teamLeadSession.user.id,
      availableActions: ["assign", "return_for_reallocation"],
      deliveryTeam: "DELIVERY_TEAM_A",
      stage: "DELIVERY_PLANNING",
    };
    let eligibleCalls = 0;
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(teamLeadSession);
      if (url.pathname.endsWith("/eligible-specialists")) {
        eligibleCalls += 1;
        return eligibleCalls === 1 ? json({ detail: "Unavailable" }, 503) : json({ items: [] });
      }
      if (url.pathname.endsWith("/work-items")) return json({ items: [planningItem] });
      if (url.pathname.includes("/requests/")) return json(requestDetail);
      throw new Error(url.pathname);
    });

    const user = userEvent.setup();
    renderApp("/delivery/team");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Eligible Analysts could not be loaded.",
    );
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("status")).toHaveTextContent(
      "No eligible Analysts are available for this team.",
    );
    expect(eligibleCalls).toBe(2);
  });

  it("does not request specialists outside delivery planning or for another owner", async () => {
    const teamLeadSession = {
      ...staffSession,
      user: {
        ...staffSession.user,
        role: "DELIVERY_TEAM_LEAD" as const,
      },
    };
    const nonPlanningItem: WorkItem = {
      ...workItem,
      assigneeDisplayName: teamLeadSession.user.displayName,
      assigneeId: teamLeadSession.user.id,
      availableActions: ["assign"],
    };
    const otherOwnerItem: WorkItem = {
      ...nonPlanningItem,
      assigneeDisplayName: "Another colleague",
      assigneeId: "another-user",
      id: "other-owner-item",
      stage: "DELIVERY_PLANNING",
    };
    let items = [nonPlanningItem, otherOwnerItem];
    let eligibleCalls = 0;
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(teamLeadSession);
      if (url.pathname.endsWith("/eligible-specialists")) {
        eligibleCalls += 1;
        return json({ items: [] });
      }
      if (url.pathname.endsWith("/work-items")) return json({ items });
      if (url.pathname.includes("/requests/")) return json(requestDetail);
      throw new Error(url.pathname);
    });

    const user = userEvent.setup();
    renderApp("/delivery/team");
    expect(await screen.findByLabelText("Lead Analyst")).toBeDisabled();
    expect(eligibleCalls).toBe(0);
    items = [otherOwnerItem];
    await user.click(
      screen.getAllByRole("button", { name: /Quarterly service readiness summary/ })[1],
    );
    expect(
      await screen.findByRole("heading", { name: "Assigned to Another colleague" }),
    ).toBeInTheDocument();
    expect(eligibleCalls).toBe(0);
  });

  it("shows assigned ownership and keeps decisions with the owner", async () => {
    const assigned = {
      ...workItem,
      assigneeId: "someone-else",
      assigneeDisplayName: "Another colleague",
    };
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(staffSession);
      if (url.pathname.endsWith("/work-items")) return json({ items: [assigned] });
      if (url.pathname.includes("/requests/")) return json(requestDetail);
      throw new Error(url.pathname);
    });
    renderApp("/triage");
    expect(
      await screen.findByRole("heading", { name: "Assigned to Another colleague" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Assigned to Another colleague", { selector: "span" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Claim work item" })).not.toBeInTheDocument();
  });

  it("reports a rejected claim and uses the anonymous owner fallback", async () => {
    const assigned = { ...workItem, assigneeId: "someone-else", assigneeDisplayName: null };
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(staffSession);
      if (url.pathname.endsWith("/work-items"))
        return json({ items: [workItem, { ...assigned, id: "second" }] });
      if (url.pathname.endsWith("/claim"))
        return json({ detail: { message: "Claim rejected." } }, 409);
      if (url.pathname.includes("/requests/")) return json(requestDetail);
      throw new Error(url.pathname);
    });
    const user = userEvent.setup();
    renderApp("/triage");
    await user.click(await screen.findByRole("button", { name: "Claim work item" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Claim rejected.");
  });

  it("recovers the queue and request context from errors", async () => {
    let listFails = true;
    let detailFails = true;
    const claimedItem = {
      ...workItem,
      assigneeDisplayName: staffSession.user.displayName,
      assigneeId: staffSession.user.id,
    };
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(staffSession);
      if (url.pathname.endsWith("/work-items"))
        return listFails ? json({ detail: "Unavailable" }, 503) : json({ items: [claimedItem] });
      if (url.pathname.includes("/requests/"))
        return detailFails ? json({ detail: "Unavailable" }, 503) : json(requestDetail);
      throw new Error(url.pathname);
    });
    const user = userEvent.setup();
    renderApp("/triage");
    expect(
      await screen.findByRole("heading", { name: "Work queue could not be loaded" }),
    ).toBeInTheDocument();
    listFails = false;
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(
      await screen.findByRole("heading", { name: "Request context could not be loaded" }),
    ).toBeInTheDocument();
    detailFails = false;
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: "Record outcome" })).toBeInTheDocument();
  });
});
