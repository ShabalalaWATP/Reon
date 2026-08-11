import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PageState } from "../components/PageState";
import { StatusJourney } from "../components/StatusJourney";
import { StatusPill } from "../components/StatusPill";
import { homeRouteForRole, navigationForRole, queueLabelForRole, roleLabels, roleRoutes } from "./routes";
import { disabledCapabilities } from "./api/capabilityClient";
import { formatDate, isComplete, requesterGroup, statusLabels, statusTone, trackingStatusLabel } from "./status";
import { protectedQueryKeys } from "./api/queryKeys";

describe("presentation helpers", () => {
  it("maps every role to a deliberately scoped route and label", () => {
    expect(roleRoutes.PLATFORM_ADMIN).toBe("/admin/users");
    expect(roleRoutes.REQUESTER).toBe("/requests");
    expect(roleLabels).toEqual({
      PLATFORM_ADMIN: "Platform Administrator",
      REQUESTER: "Customer",
      INTAKE_TRIAGE: "CRIOC Routing User",
      SERVICE_COORDINATION: "Request Coordination User",
      OPERATIONS_ALLOCATION: "Ops Routing User",
      DELIVERY_TEAM_LEAD: "Team Manager",
      DELIVERY_SPECIALIST: "Team Analyst",
      QUALITY_RELEASE: "QC Manager",
    });
    expect(navigationForRole("REQUESTER")).toEqual([
      { label: "My requests", path: "/requests" },
      { label: "New request", path: "/requests/new" },
    ]);
    expect(navigationForRole("PLATFORM_ADMIN")).toEqual([
      { label: "User accounts", path: "/admin/users" },
      { label: "Personal calendar", path: "/calendar/month" },
      { label: "Organisation directory", path: "/organisation" },
    ]);
    expect(navigationForRole("INTAKE_TRIAGE")).toEqual([
      { label: "CRIOC routing queue", path: "/triage" },
      { label: "Personal calendar", path: "/calendar/month" },
      { label: "Request tracking", path: "/tracking" },
      { label: "Organisation directory", path: "/organisation" },
    ]);
    expect(navigationForRole("DELIVERY_TEAM_LEAD")).not.toContainEqual({ label: "Request tracking", path: "/tracking" });
    expect(queueLabelForRole("REQUESTER")).toBe("Work queue");
    const enabled = {
      ...disabledCapabilities,
      myWork: true,
      configuration: true,
      products: true,
      statistics: true,
    };
    expect(homeRouteForRole("REQUESTER", disabledCapabilities)).toBe("/requests");
    expect(homeRouteForRole("REQUESTER", enabled)).toBe("/requests");
    expect(homeRouteForRole("PLATFORM_ADMIN", enabled)).toBe("/overview");
    expect(homeRouteForRole("INTAKE_TRIAGE", enabled)).toBe("/overview");
    expect(homeRouteForRole("DELIVERY_TEAM_LEAD", enabled)).toBe("/overview");
    expect(homeRouteForRole("DELIVERY_SPECIALIST", enabled)).toBe("/my-work");
    expect(homeRouteForRole("QUALITY_RELEASE", enabled)).toBe("/overview");
    expect(navigationForRole("REQUESTER", enabled)).not.toContainEqual({ label: "My assigned actions", path: "/my-work" });
    expect(navigationForRole("PLATFORM_ADMIN", enabled)).toContainEqual({ label: "Configuration", path: "/admin/configuration" });
    expect(navigationForRole("DELIVERY_SPECIALIST", enabled)).toContainEqual({ label: "Product package", path: "/product-packages/new" });
    for (const role of (Object.keys(roleRoutes) as Array<keyof typeof roleRoutes>)
      .filter((candidate) => candidate !== "REQUESTER")) {
      expect(navigationForRole(role, enabled)).toContainEqual({ label: "Personal calendar", path: "/calendar/month" });
    }
    expect(navigationForRole("INTAKE_TRIAGE", enabled, {
      statisticsAvailable: true,
      workspace: { id: "crioc", name: "CRIOC" },
    })).toEqual([
      { label: "Home", path: "/overview" },
      { label: "My assigned actions", path: "/my-work" },
      { label: "CRIOC workspace", path: "/teams/crioc/overview" },
      { label: "Personal calendar", path: "/calendar/month" },
      { label: "Request tracking", path: "/tracking" },
      { label: "Operational statistics", path: "/statistics" },
      { label: "Organisation directory", path: "/organisation" },
    ]);
  });

  it("groups and labels statuses without exposing raw values", () => {
    expect(statusLabels).toMatchObject({
      TRIAGE_REVIEW: "CRIOC routing",
      COORDINATION_REVIEW: "Request coordination",
      ALLOCATION_REVIEW: "Ops routing",
      DELIVERY_PLANNING: "Team assignment",
      IN_PROGRESS: "Product development",
      LEAD_REVIEW: "Manager review",
      QUALITY_REVIEW: "QC review",
      READY_FOR_RELEASE: "Ready for dissemination",
      COMPLETED: "Completed",
    });
    expect(statusTone("COMPLETED")).toBe("success");
    expect(statusTone("CANCELLED")).toBe("neutral");
    expect(statusTone("INFORMATION_REQUIRED")).toBe("attention");
    expect(statusTone("IN_PROGRESS")).toBe("active");
    expect(isComplete("COMPLETED")).toBe(true);
    expect(isComplete("IN_PROGRESS")).toBe(false);
    expect(requesterGroup("IN_PROGRESS", true)).toBe("Needs your input");
    expect(requesterGroup("COMPLETED", false)).toBe("Completed");
    expect(requesterGroup("IN_PROGRESS", false)).toBe("In progress");
    expect(trackingStatusLabel("COMPLETED")).toBe("Disseminated");
    expect(trackingStatusLabel("QUALITY_REVIEW")).toBe("QC review");
    expect(formatDate("2026-08-06T10:00:00Z")).toContain("06 Aug 2026");
    expect(formatDate("2026-08-06T10:00:00Z", true)).toMatch(/10:00|11:00/);
  });

  it("renders page states, pills and journey stages", () => {
    const { rerender } = render(<PageState kind="loading" title="Loading" />);
    expect(screen.getByRole("heading", { name: "Loading" })).toBeInTheDocument();
    rerender(<PageState kind="error" title="Failed">Try later</PageState>);
    expect(screen.getByText("Try later")).toBeInTheDocument();
    rerender(<PageState kind="empty" title="Empty" action={<button>Act</button>} />);
    expect(screen.getByRole("button", { name: "Act" })).toBeInTheDocument();
    rerender(<StatusPill status="COMPLETED" />);
    expect(screen.getByText("Completed")).toHaveClass("status-pill--success");
    rerender(<StatusPill label="Disseminated" status="COMPLETED" />);
    expect(screen.getByText("Disseminated")).toHaveClass("status-pill--success");
    rerender(<StatusJourney status="QUALITY_REVIEW" />);
    expect(screen.getByText("QC review").closest("li")).toHaveAttribute("aria-current", "step");
    rerender(<StatusJourney status="CANCELLED" />);
    expect(screen.getByText("Submitted").closest("li")).toHaveAttribute("aria-current", "step");
  });

  it("scopes every protected register to the authenticated identity", () => {
    expect(protectedQueryKeys.adminUsers("user-a", "")).not.toEqual(
      protectedQueryKeys.adminUsers("user-b", ""),
    );
    expect(protectedQueryKeys.adminUser("user-a", "managed")).not.toEqual(
      protectedQueryKeys.adminUser("user-b", "managed"),
    );
    expect(protectedQueryKeys.organisationUnits("user-a")).not.toEqual(
      protectedQueryKeys.organisationUnits("user-b"),
    );
    expect(protectedQueryKeys.trackedRequests("user-a")).not.toEqual(
      protectedQueryKeys.trackedRequests("user-b"),
    );
    expect(protectedQueryKeys.routingOptions("user-a", "item")).not.toEqual(
      protectedQueryKeys.routingOptions("user-b", "item"),
    );
    expect(protectedQueryKeys.statisticsScopes("user-a")).not.toEqual(
      protectedQueryKeys.statisticsScopes("user-b"),
    );
    expect(protectedQueryKeys.statistics("user-a", "scope", "unit", "from", "to", "UTC")).not.toEqual(
      protectedQueryKeys.statistics("user-b", "scope", "unit", "from", "to", "UTC"),
    );
    expect(protectedQueryKeys.teamWorkspaces("user-a")).not.toEqual(
      protectedQueryKeys.teamWorkspaces("user-b"),
    );
    expect(protectedQueryKeys.teamPeople("user-a", "team")).not.toEqual(
      protectedQueryKeys.teamPeople("user-b", "team"),
    );
  });
});
