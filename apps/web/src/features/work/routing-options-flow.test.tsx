import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";

import type { WorkAction, WorkItem } from "../../lib/api/types";
import {
  organisationChildren,
  organisationUnit,
  requestDetail,
  staffSession,
  workItem,
} from "../../test/fixtures";
import { json, mockFetch, renderApp } from "../../test/render";
import type { RoutingOptions } from "./RoutingDestinationField";
import { WorkActionForm } from "./WorkActionForm";

const teamOptions: RoutingOptions = {
  items: organisationChildren("ACSA_B_OPS").map((unit) =>
    unit.code === "CEDAR_TEAM" ? { ...unit, staffingStatus: "UNSTAFFED" } : unit,
  ),
  onRetry: vi.fn(),
  status: "ready",
};

const commandRoute = ["CRIOC", "JOCK"].map((code) => {
  const { id, kind, name } = organisationUnit(code);
  return { id, code, kind, name };
});

describe("dynamic routing destinations", () => {
  it.each([
    ["progress", "CRIOC", ["JOCK", "SYGOC", "MYGOC"]],
    ["send_to_allocation", "JOCK", ["ACSA-B Ops", "Aurora Ops", "Vertex Ops"]],
    ["allocate", "ACSA_B_OPS", ["SSG Team", "Cedar Team", "Quartz Team"]],
  ] as const)("keeps every direct child enabled for %s", (action, parentCode, expectedNames) => {
    const items = organisationChildren(parentCode);
    expect(items.map((item) => item.name)).toEqual(expectedNames);
    render(
      <WorkActionForm
        actions={[action]}
        disabled={false}
        onSubmit={vi.fn()}
        routingOptions={{ items, onRetry: vi.fn(), status: "ready" }}
      />,
    );

    const destination = screen.getByLabelText("Destination unit");
    const displayedOptions = within(destination).getAllByRole("option").slice(1);
    expect(displayedOptions).toHaveLength(expectedNames.length);
    for (const name of expectedNames) {
      const option = displayedOptions.find((candidate) =>
        candidate.textContent?.startsWith(`${name} ·`),
      );
      expect(option).toBeDefined();
      expect(option).toBeEnabled();
    }
  });

  it("associates destination errors without retaining stale descriptions", async () => {
    const user = userEvent.setup();
    const view = render(
      <WorkActionForm
        actions={["send_to_allocation"]}
        disabled={false}
        onSubmit={vi.fn()}
        routingOptions={{
          items: organisationChildren("JOCK"),
          onRetry: vi.fn(),
          status: "ready",
        }}
      />,
    );
    const destination = screen.getByLabelText("Destination unit");
    expect(destination).toHaveAttribute("aria-invalid", "false");
    expect(destination).not.toHaveAttribute("aria-describedby");

    await user.click(screen.getByRole("button", { name: "Route to Ops group" }));
    const error = await screen.findByText("Choose a destination unit.");
    expect(error.id).not.toBe("");
    expect(destination).toHaveAttribute("aria-invalid", "true");
    expect(destination).toHaveAttribute("aria-describedby", error.id);
    expect(await axe(view.container)).toHaveNoViolations();

    await user.click(screen.getByRole("button", { name: "Route to Ops group" }));
    expect(screen.getByText("Choose a destination unit.")).toHaveAttribute("id", error.id);
    await user.selectOptions(destination, organisationUnit("ACSA_B_OPS").id);
    expect(destination).toHaveAttribute("aria-invalid", "false");
    expect(destination).not.toHaveAttribute("aria-describedby");
  });

  it("shows route context and filters only the authorised direct children", async () => {
    const submit = vi.fn<(action: WorkAction) => void>();
    const user = userEvent.setup();
    const view = render(
      <WorkActionForm
        actions={["send_to_allocation"]}
        disabled={false}
        onSubmit={submit}
        routingOptions={{
          items: organisationChildren("JOCK"),
          onRetry: vi.fn(),
          route: commandRoute,
          status: "ready",
        }}
      />,
    );

    const path = screen.getByRole("navigation", { name: "Current routing path" });
    expect(path).toHaveTextContent("CRIOC");
    expect(path).toHaveTextContent("JOCK");
    const search = screen.getByRole("searchbox", { name: "Find destination" });
    const destination = screen.getByLabelText("Destination unit");
    await user.selectOptions(destination, organisationUnit("AURORA_OPS").id);
    await user.type(search, "vertex_ops");
    expect(screen.getByText("1 of 3 destinations shown")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /Vertex Ops/ })).toBeEnabled();
    expect(screen.getByRole("group", { name: "Selected destination" })).toHaveTextContent(
      "Aurora Ops",
    );
    expect(destination).toHaveValue(organisationUnit("AURORA_OPS").id);
    await user.type(
      screen.getByLabelText("Routing note"),
      "Retain the selected route while searching.",
    );
    await user.click(screen.getByRole("button", { name: "Route to Ops group" }));
    expect(submit).toHaveBeenCalledWith({
      action: "send_to_allocation",
      destinationUnitId: organisationUnit("AURORA_OPS").id,
      note: "Retain the selected route while searching.",
    });
    await user.clear(search);
    expect(screen.getByText("3 of 3 destinations shown")).toBeInTheDocument();
    expect(screen.getByText(/Selected route:/)).toHaveTextContent(
      "CRIOC › JOCK › Aurora Ops (AURORA_OPS)",
    );
    expect(await axe(view.container)).toHaveNoViolations();
  });

  it("keeps every valid team selectable and warns after choosing an unstaffed team", async () => {
    const submit = vi.fn<(action: WorkAction) => void>();
    const user = userEvent.setup();
    render(
      <WorkActionForm
        actions={["allocate"]}
        disabled={false}
        onSubmit={submit}
        routingOptions={teamOptions}
      />,
    );

    const staffed = screen.getByRole("option", { name: /SSG Team/ });
    const unstaffed = screen.getByRole("option", { name: /Cedar Team/ });
    expect(staffed).toBeEnabled();
    expect(unstaffed).toBeEnabled();
    await user.selectOptions(
      screen.getByLabelText("Destination unit"),
      organisationUnit("CEDAR_TEAM").id,
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Cedar Team is unstaffed. Work will await staffing after routing.",
    );
    await user.type(screen.getByLabelText("Required capabilities"), "Research\nWriting");
    await user.click(screen.getByRole("button", { name: "Route to team" }));
    expect(submit).toHaveBeenCalledWith({
      action: "allocate",
      destinationUnitId: "unit-cedar",
      requiredCapabilities: ["Research", "Writing"],
    });
  });

  it("renders loading, error and empty destination states", async () => {
    const retry = vi.fn();
    const user = userEvent.setup();
    const { rerender } = render(
      <WorkActionForm
        actions={["progress"]}
        disabled={false}
        onSubmit={vi.fn()}
        routingOptions={{ items: [], onRetry: retry, status: "loading" }}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Loading valid destinations…");
    expect(screen.getByLabelText("Destination unit")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Route to command" })).toBeDisabled();

    rerender(
      <WorkActionForm
        actions={["progress"]}
        disabled={false}
        onSubmit={vi.fn()}
        routingOptions={{ items: [], onRetry: retry, status: "error" }}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Valid destinations could not be loaded.");
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledOnce();

    rerender(
      <WorkActionForm
        actions={["progress"]}
        disabled={false}
        onSubmit={vi.fn()}
        routingOptions={{ items: [], onRetry: retry, status: "ready" }}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "No valid destinations are configured for this task.",
    );
  });

  it("loads options only after a routing task is claimed by the current user", async () => {
    let item: WorkItem = workItem;
    let routingCalls = 0;
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(staffSession);
      if (url.pathname.endsWith("/work-items")) return json({ items: [item] });
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
        routingCalls += 1;
        return json({
          items: organisationChildren("CRIOC"),
          route: [organisationUnit("CRIOC")],
        });
      }
      if (url.pathname.includes("/requests/")) return json(requestDetail);
      throw new Error(url.pathname);
    });
    const user = userEvent.setup();
    renderApp("/triage");
    await screen.findByRole("button", { name: "Claim work item" });
    expect(routingCalls).toBe(0);
    await user.click(screen.getByRole("button", { name: "Claim work item" }));
    await user.selectOptions(await screen.findByLabelText("Outcome"), "progress");
    expect(await screen.findByRole("option", { name: /JOCK/ })).toBeEnabled();
    expect(screen.getByRole("option", { name: /SYGOC/ })).toBeEnabled();
    expect(screen.getByRole("option", { name: /MYGOC/ })).toBeEnabled();
    expect(screen.getByRole("navigation", { name: "Current routing path" })).toHaveTextContent(
      "CRIOC",
    );
    expect(routingCalls).toBe(1);
  });

  it("does not load destinations for a claimed non-routing action", async () => {
    const approvedItem = {
      ...workItem,
      assigneeId: staffSession.user.id,
      assigneeDisplayName: staffSession.user.displayName,
      availableActions: ["approve"] as const,
      stage: "LEAD_REVIEW" as const,
    };
    let routingCalls = 0;
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(staffSession);
      if (url.pathname.endsWith("/work-items")) return json({ items: [approvedItem] });
      if (url.pathname.endsWith("/routing-options")) routingCalls += 1;
      if (url.pathname.includes("/requests/")) return json(requestDetail);
      throw new Error(url.pathname);
    });
    renderApp("/triage");
    expect(await screen.findByRole("button", { name: "Approve" })).toBeInTheDocument();
    expect(routingCalls).toBe(0);
  });
});
