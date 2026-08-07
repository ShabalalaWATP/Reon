import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import type {
  StatisticsEvolution,
  StatisticsEvolutionFilters,
} from "../../lib/api/statisticsEvolutionTypes";
import { adminSession } from "../../test/fixtures";
import { json, mockFetch, TestProviders } from "../../test/render";
import { StatisticsEvolutionContainer } from "./StatisticsEvolutionContainer";
import { StatisticsEvolutionView } from "./StatisticsEvolutionView";
import { StatisticsExportPanel } from "./StatisticsExportPanel";

const filters: StatisticsEvolutionFilters = {
  scopeId: "platform",
  from: "2026-08-01",
  to: "2026-08-07",
  timeZone: "Europe/London",
};

const evolution: StatisticsEvolution = {
  scope: {
    id: "platform",
    unitId: null,
    name: "Whole platform",
    kind: "PLATFORM",
    includeDescendants: true,
  },
  range: {
    fromDate: filters.from,
    toDate: filters.to,
    timeZone: filters.timeZone,
    asOfDate: filters.to,
  },
  freshness: {
    health: "READY",
    lastProjectedAt: "2026-08-07T10:30:00Z",
    sourceEventCount: 42,
    projectedRequestCount: 18,
  },
  comparison: [
    { key: "received", label: "Received", current: 12, previous: 8, change: 4, unit: "count", suppressed: false },
    { key: "completion", label: "Completion", current: 75, previous: 80, change: -5, unit: "percentage", suppressed: false },
    { key: "duration", label: "Lead time", current: 14, previous: 15, change: -1, unit: "hours", suppressed: false },
    { key: "unavailable", label: "Unavailable comparison", current: null, previous: null, change: null, unit: "count", suppressed: false },
    { key: "stable", label: "Stable demand", current: 5, previous: 4, change: 1, unit: "count", suppressed: false },
    { key: "small", label: "Small cohort", current: null, previous: null, change: null, unit: "count", suppressed: true },
  ],
  bottlenecks: [
    { key: "manager", label: "Manager review", activeCount: 4, medianAgeHours: 8, p90AgeHours: 26, overdueCount: 1, suppressed: false },
    { key: "quality", label: "Quality review", activeCount: 2, medianAgeHours: 4, p90AgeHours: 12, overdueCount: 0, suppressed: false },
    { key: "allocation", label: "Team allocation", activeCount: 3, medianAgeHours: 9, p90AgeHours: 30, overdueCount: 1, suppressed: false },
  ],
  capacity: [
    { date: "2026-08-06", availableMinutes: 1_200, reservedMinutes: 240, activeWorkMinutes: 600, projectedDemandMinutes: 900, estimate: true },
    { date: "2026-08-07", availableMinutes: 1_080, reservedMinutes: 180, activeWorkMinutes: 540, projectedDemandMinutes: 780, estimate: false },
  ],
  releases: [
    { key: "released", label: "Products released", count: 5, medianHours: 18, suppressed: false },
    { key: "replaced", label: "Products replaced", count: 1, medianHours: null, suppressed: false },
  ],
  notifications: [
    { key: "routing", label: "Routing actions", count: 9, medianResponseHours: 2, unresolvedCount: 2, suppressed: false },
    { key: "release", label: "Release actions", count: 4, medianResponseHours: null, unresolvedCount: 1, suppressed: false },
  ],
  iterations: [
    { key: "pilot", label: "Pilot iteration", committedCount: 8, completedCount: 6, completionPercentage: 75, suppressed: false },
    { key: "new", label: "New iteration", committedCount: 0, completedCount: 0, completionPercentage: null, suppressed: false },
  ],
  projection: {
    label: "Deterministic estimate from authorised aggregate facts",
    estimate: true,
    periods: [
      { date: "2026-08-08", demandCount: 10, capacityCount: 8 },
      { date: "2026-08-09", demandCount: 6, capacityCount: 7 },
    ],
  },
  exports: {
    csv: { state: "AVAILABLE", reason: "Aggregate cohort is large enough." },
    pdf: { state: "DENIED", reason: "PDF export is not granted for this scope." },
  },
};

describe("enhanced scoped statistics", () => {
  it("keeps chart, table and textual summaries aligned and exports only when allowed", async () => {
    const exportBodies: Array<Record<string, unknown>> = [];
    mockFetch((url, init) => {
      if (url.pathname.endsWith("/statistics/exports")) {
        exportBodies.push(JSON.parse(String(init.body)) as Record<string, unknown>);
        return json({ state: "READY", downloadUrl: "/api/v1/statistics/exports/export-one", expiresAt: "2026-08-07T11:00:00Z", message: "Aggregate CSV is ready." });
      }
      throw new Error(`Unexpected ${url.pathname}`);
    });
    const user = userEvent.setup();
    const view = render(<TestProviders><StatisticsEvolutionView data={evolution} filters={filters} session={adminSession} /></TestProviders>);

    expect(screen.getByRole("table", { name: "Period comparison data" })).toHaveTextContent("Small cohortSuppressedSuppressedSuppressed");
    expect(screen.getByRole("table", { name: "Stage bottlenecks data" })).toHaveTextContent("Manager review");
    expect(screen.getByRole("table", { name: "Capacity and demand data" })).toHaveTextContent("Estimate");
    expect(screen.getByRole("table", { name: "Release cycle data" })).toHaveTextContent("Products replaced");
    expect(screen.getByRole("table", { name: "Notification response data" })).toHaveTextContent("Routing actions");
    expect(screen.getByRole("table", { name: "Iteration commitments data" })).toHaveTextContent("75%");
    expect(screen.getByRole("table", { name: "Demand projection data" })).toHaveTextContent("Estimated demand");
    expect(screen.getByText(/largest absolute change at -5%/)).toBeInTheDocument();
    expect(screen.getByText(/longest 90th-percentile active age at 30 hours/)).toBeInTheDocument();
    expect(screen.getByText(/3 unresolved actions/)).toBeInTheDocument();
    expect(screen.queryByText(/Analyst ranking/i)).not.toBeInTheDocument();

    expect(screen.getByRole("button", { name: "Prepare PDF" })).toBeDisabled();
    expect(screen.getByText(/DENIED: PDF export/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Prepare CSV" }));
    const link = await screen.findByRole("link", { name: "Download aggregate export" });
    expect(link).toHaveAttribute("href", "/api/v1/statistics/exports/export-one");
    expect(exportBodies[0]).toMatchObject({ ...filters, format: "CSV" });
    expect(await axe(view.container)).toHaveNoViolations();
  });

  it("uses explicit suppressed, empty, stale and unavailable summaries", () => {
    const suppressed = { ...evolution,
      freshness: { ...evolution.freshness, health: "REBUILDING" as const, lastProjectedAt: null },
      comparison: [{ ...evolution.comparison.at(-1)! }],
      bottlenecks: [{ ...evolution.bottlenecks[0], activeCount: null, medianAgeHours: null, p90AgeHours: null, overdueCount: null, suppressed: true }],
      capacity: [],
      releases: [{ ...evolution.releases[0], count: null, medianHours: null, suppressed: true }],
      notifications: [{ ...evolution.notifications[0], count: null, medianResponseHours: null, unresolvedCount: null, suppressed: true }],
      iterations: [{ ...evolution.iterations[0], committedCount: null, completedCount: null, completionPercentage: null, suppressed: true }],
      projection: { ...evolution.projection, periods: [] },
      exports: { csv: { state: "SUPPRESSED" as const, reason: "Small cohort." }, pdf: { state: "PENDING" as const, reason: "Policy refresh pending." } },
    };
    render(<TestProviders><StatisticsEvolutionView data={suppressed} filters={filters} session={adminSession} /></TestProviders>);
    expect(screen.getAllByText(/No unsuppressed/)).toHaveLength(5);
    expect(screen.getByText("No capacity trend is available.")).toBeInTheDocument();
    expect(screen.getByText(/No projection periods are available/)).toBeInTheDocument();
    expect(screen.getAllByText("No aggregate records in this period.")).toHaveLength(2);
    expect(screen.getAllByText(/not yet projected/)).toHaveLength(8);
    expect(screen.getByText("SUPPRESSED: Small cohort.")).toBeInTheDocument();
    expect(screen.getByText("PENDING: Policy refresh pending.")).toBeInTheDocument();
  });

  it("retries projection reads and exposes pending, unsafe and failed export states", async () => {
    let dashboardAttempts = 0;
    mockFetch((url, init) => {
      if (url.pathname.endsWith("/statistics/evolution")) {
        dashboardAttempts += 1;
        return dashboardAttempts === 1 ? json({ detail: "Unavailable" }, 503) : json(evolution);
      }
      if (url.pathname.endsWith("/statistics/exports")) {
        const format = (JSON.parse(String(init.body)) as { format: string }).format;
        if (format === "PDF") return json({ state: "PENDING", downloadUrl: null, expiresAt: null, message: "Export queued." });
        if (dashboardAttempts === 2) { dashboardAttempts += 1; return json({ state: "READY", downloadUrl: "https://unsafe.example/export", expiresAt: null, message: "Ready." }); }
        return json({ detail: "Export unavailable" }, 503);
      }
      throw new Error(`Unexpected ${url.pathname}`);
    });
    const user = userEvent.setup();
    render(<TestProviders><StatisticsEvolutionContainer filters={filters} session={adminSession} /></TestProviders>);
    expect(await screen.findByText("Enhanced measures unavailable")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try enhanced measures again" }));
    expect(await screen.findByRole("heading", { name: "Period comparison" })).toBeInTheDocument();

    const availablePolicies = { csv: { state: "AVAILABLE" as const, reason: "Allowed." }, pdf: { state: "AVAILABLE" as const, reason: "Allowed." } };
    const exportView = render(<TestProviders><StatisticsExportPanel filters={filters} policies={availablePolicies} session={adminSession} /></TestProviders>);
    await user.click(withinView(exportView.container, "Prepare PDF"));
    expect(await withinText(exportView.container, "Export pending")).toBeInTheDocument();
    await user.click(withinView(exportView.container, "Prepare CSV"));
    expect(await withinText(exportView.container, "Download address rejected by the client safety policy.")).toBeInTheDocument();
    await user.click(withinView(exportView.container, "Prepare CSV"));
    await waitFor(() => expect(exportView.container.querySelector("[role='alert']")).toHaveTextContent("Export unavailable"));
  });
});

function withinView(container: HTMLElement, name: string) {
  const button = Array.from(container.querySelectorAll("button")).find((item) => item.textContent === name);
  if (!button) throw new Error(`Missing ${name}`);
  return button;
}

async function withinText(container: HTMLElement, value: string) {
  await waitFor(() => expect(container).toHaveTextContent(value));
  const item = Array.from(container.querySelectorAll("strong, span")).find((element) => element.textContent === value);
  if (!item) throw new Error(`Missing ${value}`);
  return item;
}
