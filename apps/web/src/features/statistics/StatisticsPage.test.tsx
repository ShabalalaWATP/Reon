import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import type {
  StatisticsDashboard,
  StatisticsScope,
} from "../../lib/api/statisticsTypes";
import { adminSession, enabledCapabilities } from "../../test/fixtures";
import { json, mockFeatureFetch, renderApp } from "../../test/render";
import { CategoryPanel } from "./StatisticsVisuals";

const platformScope: StatisticsScope = {
  id: "platform",
  unitId: "00000000-0000-4000-8000-000000000001",
  name: "Whole platform",
  kind: "PLATFORM",
  includeDescendants: true,
  units: [
    { id: "00000000-0000-4000-8000-000000000001", parentId: null, name: "JIOC", kind: "ROOT", depth: 0 },
    { id: "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee", parentId: "00000000-0000-4000-8000-000000000001", name: "DIGOC", kind: "COMMAND", depth: 1 },
    { id: "ffffffff-bbbb-4ccc-8ddd-eeeeeeeeeeee", parentId: "00000000-0000-4000-8000-000000000001", name: "SYGOC", kind: "COMMAND", depth: 1 },
  ],
};
const commandScope: StatisticsScope = {
  id: "command-digoc",
  unitId: "11111111-2222-4333-8444-555555555555",
  name: "NCGI-A Ops",
  kind: "OPS_GROUP",
  includeDescendants: true,
  units: [{ id: "11111111-2222-4333-8444-555555555555", parentId: null, name: "NCGI-A Ops", kind: "OPS_GROUP", depth: 0 }],
};

const dashboard: StatisticsDashboard = {
  scope: platformScope,
  selectedUnit: platformScope.units[0],
  breadcrumb: platformScope.units,
  range: {
    fromDate: "2026-08-01",
    toDate: "2026-08-07",
    timeZone: "Europe/London",
    asOfDate: "2026-08-07",
  },
  freshness: {
    health: "READY",
    lastProjectedAt: "2026-08-07T10:30:00Z",
    sourceEventCount: 22,
    projectedRequestCount: 8,
  },
  definitions: [
    { key: "active", label: "Active", description: "Requests not yet completed or closed." },
  ],
  summary: [
    { key: "received", label: "Received", value: 8, unit: "count", suppressed: false },
    { key: "completed", label: "Completed", value: 25, unit: "percentage", suppressed: false },
    { key: "rating", label: "Average rating", value: 4.6, unit: "rating", suppressed: false },
    { key: "clarification", label: "Clarification time", value: 2.5, unit: "hours", suppressed: false },
    { key: "unavailable", label: "Unavailable", value: null, unit: "count", suppressed: false },
    { key: "small-rating", label: "Small cohort rating", value: null, unit: "rating", suppressed: true },
  ],
  status: [
    { key: "active", label: "Active", count: 6 },
    { key: "completed", label: "Completed", count: 2 },
  ],
  age: [
    { key: "under-seven", label: "Under 7 days", count: 4 },
    { key: "seven-plus", label: "7 days or more", count: 2 },
  ],
  dueRisk: [
    { key: "overdue", label: "Overdue", count: 1 },
    { key: "on-track", label: "On track", count: 5 },
  ],
  throughputResolution: "DAILY",
  throughput: [
    { date: "2026-08-06", received: 3, completed: 1 },
    { date: "2026-08-07", received: 1, completed: 2 },
  ],
  stageDurations: [
    { key: "delivery", label: "Delivery", completedIntervals: 5, medianHours: 12, p90Hours: 22 },
  ],
  children: [
    {
      unitId: "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
      name: "DIGOC",
      kind: "COMMAND",
      received: 6,
      active: 4,
      completed: 2,
      overdue: 1,
      feedbackCount: 5,
      averageRating: 4.6,
      ratingSuppressed: false,
    },
    {
      unitId: "ffffffff-bbbb-4ccc-8ddd-eeeeeeeeeeee",
      name: "SYGOC",
      kind: "COMMAND",
      received: 2,
      active: 2,
      completed: 0,
      overdue: 0,
      feedbackCount: 1,
      averageRating: null,
      ratingSuppressed: true,
    },
  ],
};

describe("operational statistics", () => {
  it("renders a neutral donut when a populated category set totals zero", () => {
    const view = render(
      <CategoryPanel rows={[{ key: "none", label: "No overdue work", count: 0 }]} title="Due-date risk" />,
    );

    expect(view.container.querySelector(".donut-chart")).toHaveStyle({
      background: "var(--surface-strong)",
    });
    expect(screen.getByRole("table", { name: "Due-date risk data" })).toHaveTextContent("No overdue work");
  });

  it("shows only granted scopes with accessible chart-table parity", async () => {
    const requestedScopes: string[] = [];
    const requestedUnits: string[] = [];
    mockFeatureFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(adminSession);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/statistics/scopes")) {
        return json({ items: [platformScope, commandScope] });
      }
      if (url.pathname.endsWith("/statistics")) {
        requestedScopes.push(url.searchParams.get("scopeId") ?? "");
        requestedUnits.push(url.searchParams.get("unitId") ?? "");
        const selectedScope = requestedScopes.at(-1) === commandScope.id ? commandScope : platformScope;
        const selectedUnit = selectedScope.units.find((unit) => unit.id === requestedUnits.at(-1)) ?? selectedScope.units[0];
        return json({
          ...dashboard,
          scope: selectedScope,
          selectedUnit,
          breadcrumb: selectedUnit.parentId ? [selectedScope.units[0], selectedUnit] : [selectedUnit],
        });
      }
      throw new Error(`Unexpected ${url.pathname}`);
    }, true, false);
    const user = userEvent.setup();
    const view = renderApp(`/statistics?scopeId=platform&unitId=${platformScope.units[2].id}`);

    expect(await screen.findByRole("heading", { name: "Statistics" })).toBeInTheDocument();
    expect(await screen.findByText("Projection current")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Operational statistics" })).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Summary measures" })).getByText("8")).toBeInTheDocument();
    expect(screen.getByLabelText("Organisation")).toHaveValue(platformScope.units[2].id);
    expect(screen.getByRole("table", { name: "Current status data" })).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Daily throughput data" })).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Direct child unit comparison data" })).toHaveTextContent("SYGOC");
    expect(view.container.querySelectorAll(".donut-chart")).toHaveLength(3);
    expect(view.container.querySelector(".duration-range-chart")).toBeInTheDocument();
    expect(await axe(view.container)).toHaveNoViolations();

    await user.click(screen.getByRole("button", { name: "View DIGOC statistics" }));
    await waitFor(() => expect(requestedUnits).toContain("aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"));
    expect(screen.getByLabelText("Organisation")).toHaveValue("aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee");

    await user.selectOptions(screen.getByLabelText("Reporting root"), commandScope.id);
    await waitFor(() => expect(requestedScopes).toContain(commandScope.id));
    expect(await screen.findByText("NCGI-A Ops", { selector: ".statistics-filters option" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("From"), { target: { value: "2099-12-31" } });
    expect(screen.getByRole("alert")).toHaveTextContent("start date");
  });

  it("handles unavailable access and retries scope failures", async () => {
    let scopeAttempts = 0;
    mockFeatureFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(adminSession);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/statistics/scopes")) {
        scopeAttempts += 1;
        return scopeAttempts === 1 ? json({ detail: "Unavailable" }, 503) : json({ items: [] });
      }
      throw new Error(`Unexpected ${url.pathname}`);
    }, true, false);
    const user = userEvent.setup();
    renderApp("/statistics");
    await user.click(await screen.findByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: "No statistics scope assigned" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Operational statistics" })).not.toBeInTheDocument();
  });

  it("reports dashboard failures and renders an empty degraded projection", async () => {
    let dashboardAttempts = 0;
    mockFeatureFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(adminSession);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/statistics/scopes")) return json({ items: [platformScope] });
      if (url.pathname.endsWith("/statistics")) {
        dashboardAttempts += 1;
        if (dashboardAttempts === 1) return json({ detail: "Unavailable" }, 503);
        return json({
          ...dashboard,
          summary: dashboard.summary.map((metric) => metric.key === "received" ? { ...metric, value: null } : metric),
          freshness: { health: "REBUILDING", lastProjectedAt: null, sourceEventCount: 0, projectedRequestCount: 0 },
          status: [],
          age: [],
          dueRisk: [],
          throughput: [],
          stageDurations: [],
          children: [],
        });
      }
      throw new Error(`Unexpected ${url.pathname}`);
    }, true, false);
    const user = userEvent.setup();
    renderApp("/statistics");
    await user.click(await screen.findByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Projection degraded")).toBeInTheDocument();
    expect(screen.getByText(/not yet projected/)).toBeInTheDocument();
    expect(screen.getAllByText("No records in this period.")).toHaveLength(3);
    expect(screen.getByText("No completed stages in this period.")).toBeInTheDocument();
    expect(screen.queryByRole("table", { name: "Direct child unit comparison data" })).not.toBeInTheDocument();
  });
});
