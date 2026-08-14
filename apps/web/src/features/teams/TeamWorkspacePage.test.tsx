import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import { enabledCapabilities } from "../../test/fixtures";
import { json, mockFeatureFetch, renderApp } from "../../test/render";
import {
  analystAccess,
  analystSession,
  managerAccess,
  managerSession,
  mockTeamApi,
  people,
  eligible,
} from "./teamWorkspaceTestSupport";

describe("team workspace", () => {
  it("provides an accessible overview, all workspace views and immutable activity", async () => {
    mockTeamApi(managerSession, managerAccess);
    const user = userEvent.setup();
    const view = renderApp("/teams/team-ssg/overview");
    expect(await screen.findByRole("heading", { name: "SSG Team" })).toBeInTheDocument();
    const staffing = await screen.findByRole("region", { name: "Workspace staffing" });
    expect(within(staffing).getByText("Managers").closest("div")).toHaveTextContent("3");
    expect(screen.getByRole("heading", { name: "Team attention" })).toBeInTheDocument();
    expect(
      await screen.findByText("Research, Data analysis", { exact: false }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Upcoming team calendar" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "SSG Team workspace" })).toBeInTheDocument();
    expect(
      within(screen.getByRole("navigation", { name: "Organisation workspace views" })).getAllByRole(
        "link",
      ),
    ).toHaveLength(7);
    expect(await axe(view.container)).toHaveNoViolations();

    const tabs = screen.getByRole("navigation", { name: "Organisation workspace views" });
    expect(within(tabs).getByRole("link", { name: "Board" })).toHaveAttribute(
      "href",
      "/teams/team-ssg/board",
    );
    expect(within(tabs).getByRole("link", { name: "Calendar" })).toHaveAttribute(
      "href",
      "/teams/team-ssg/calendar",
    );
    expect(within(tabs).getByRole("link", { name: "Work queue" })).toHaveAttribute(
      "href",
      "/teams/team-ssg/queue",
    );
    expect(within(tabs).queryByRole("link", { name: "Planning" })).not.toBeInTheDocument();
    expect(within(tabs).queryByRole("link", { name: "Handover" })).not.toBeInTheDocument();
    await user.click(within(tabs).getByRole("link", { name: "Activity" }));
    expect(
      await screen.findByText(
        "A scheduled Analyst transfer became effective.",
        {},
        { timeout: 5_000 },
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/scheduled membership service/)).toBeInTheDocument();
  });

  it("lets an exact-team Manager add, transfer and end Analysts with mandatory evidence", async () => {
    const bodies: Array<Record<string, unknown>> = [];
    mockTeamApi(managerSession, managerAccess, bodies);
    const user = userEvent.setup();
    renderApp("/teams/team-ssg/people");
    expect(await screen.findByRole("heading", { name: "People" })).toBeInTheDocument();
    expect(screen.getByText("The Analyst transferred to another team.")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "End membership" })[0]).toBeEnabled();
    expect(screen.getAllByRole("button", { name: "End membership" })[1]).toBeDisabled();

    await user.selectOptions(screen.getByLabelText(/^Member/), "alan");
    await user.type(
      screen.getByLabelText(/^Reason/),
      "Alan is joining to balance current delivery demand.",
    );
    await user.click(screen.getByRole("button", { name: "Add Member" }));
    await waitFor(() => expect(bodies.some((body) => body.analystId === "alan")).toBe(true));

    await user.click(screen.getByRole("button", { name: "Schedule transfer" }));
    await user.selectOptions(screen.getByLabelText(/^Member/), "beth");
    fireEvent.change(screen.getByLabelText(/Effective date/), {
      target: { value: "2026-08-20T10:00" },
    });
    await user.type(
      screen.getByLabelText(/^Reason/),
      "Beth will transfer after the current planning cycle.",
    );
    await user.click(screen.getByRole("button", { name: "Confirm transfer" }));
    await waitFor(() =>
      expect(bodies.some((body) => body.currentMembershipId === "membership-beth")).toBe(true),
    );

    await user.click(screen.getAllByRole("button", { name: "End membership" })[0]);
    await user.type(
      screen.getByLabelText(/Reason for ending/),
      "Lewis is moving after all assigned work was completed.",
    );
    await user.click(screen.getByRole("button", { name: "Confirm end" }));
    await waitFor(() =>
      expect(bodies.some((body) => body.expectedVersion === 2 && !body.analystId)).toBe(true),
    );
  });

  it("keeps Analysts read-only and handles unavailable, missing and invalid workspace routes", async () => {
    mockTeamApi(analystSession, analystAccess);
    renderApp("/teams/team-ssg/people");
    expect(await screen.findByText("Lewis Ferguson")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Change roster" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "End membership" })).not.toBeInTheDocument();

    mockTeamApi(analystSession, analystAccess);
    renderApp("/teams/team-other/overview");
    expect(
      await screen.findByRole("heading", { name: "Team workspace unavailable" }),
    ).toBeInTheDocument();

    mockTeamApi(analystSession, analystAccess);
    renderApp("/teams/team-ssg/not-a-view");
    expect(await screen.findByRole("heading", { name: "Team attention" })).toBeInTheDocument();
  });

  it("reports an empty assignment and recovers workspace and overview queries", async () => {
    mockFeatureFetch(async (url) => {
      if (url.pathname.endsWith("/auth/me")) return json(managerSession);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      throw new Error(`Unexpected ${url.pathname}`);
    });
    renderApp("/teams/team-ssg/overview");
    expect(
      await screen.findByRole("heading", { name: "No team workspace assigned" }),
    ).toBeInTheDocument();

    let workspaceAttempts = 0;
    let overviewAttempts = 0;
    const quartz = {
      ...managerAccess,
      teamId: "team-quartz",
      teamCode: "QUARTZ_TEAM",
      teamName: "Quartz Team",
    };
    mockFeatureFetch(
      async (url) => {
        if (url.pathname.endsWith("/auth/me")) return json(managerSession);
        if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
        if (url.pathname.endsWith("/team-workspaces")) {
          workspaceAttempts += 1;
          return workspaceAttempts === 1
            ? json({ detail: "Unavailable" }, 503)
            : json({ items: [managerAccess, quartz] });
        }
        if (url.pathname.endsWith("/team-workspaces/team-ssg")) {
          overviewAttempts += 1;
          return overviewAttempts === 1
            ? json({ detail: "Unavailable" }, 503)
            : json({
                access: managerAccess,
                managerCount: 2,
                analystCount: 4,
                activeWorkCount: 1,
                dueSoonCount: 0,
                overdueCount: 0,
              });
        }
        if (url.pathname.endsWith("/team-workspaces/team-quartz"))
          return json({
            access: quartz,
            managerCount: 1,
            analystCount: 2,
            activeWorkCount: 0,
            dueSoonCount: 0,
            overdueCount: 0,
          });
        throw new Error(`Unexpected ${url.pathname}`);
      },
      true,
      true,
      false,
    );
    const user = userEvent.setup();
    renderApp("/teams/team-ssg/overview");
    expect(
      await screen.findByRole("heading", { name: "Team workspace could not be loaded" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(workspaceAttempts).toBe(2));
    expect(
      await screen.findByRole("heading", { name: "Team home could not be loaded" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: "Team attention" })).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Workspace"), "team-quartz");
    expect(await screen.findByRole("heading", { name: "Quartz Team" })).toBeInTheDocument();
  });

  it("recovers activity, people and roster-option errors and reports failed changes", async () => {
    let activityAttempts = 0;
    mockFeatureFetch(
      async (url) => {
        if (url.pathname.endsWith("/auth/me")) return json(managerSession);
        if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
        if (url.pathname.endsWith("/team-workspaces")) return json({ items: [managerAccess] });
        if (url.pathname.endsWith("/activity")) {
          activityAttempts += 1;
          return activityAttempts === 1
            ? json({ detail: "Unavailable" }, 503)
            : json({ items: [] });
        }
        throw new Error(`Unexpected ${url.pathname}`);
      },
      true,
      true,
      false,
    );
    const user = userEvent.setup();
    renderApp("/teams/team-ssg/activity");
    expect(
      await screen.findByRole("heading", { name: "Team activity could not be loaded" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(
      await screen.findByRole("heading", { name: "No team activity recorded" }),
    ).toBeInTheDocument();

    let peopleAttempts = 0;
    let eligibleAttempts = 0;
    mockFeatureFetch(
      async (url) => {
        if (url.pathname.endsWith("/auth/me")) return json(managerSession);
        if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
        if (url.pathname.endsWith("/team-workspaces")) return json({ items: [managerAccess] });
        if (url.pathname.endsWith("/people")) {
          peopleAttempts += 1;
          return peopleAttempts === 1
            ? json({ detail: "Unavailable" }, 503)
            : json({ items: people });
        }
        if (url.pathname.endsWith("/eligible-analysts")) {
          eligibleAttempts += 1;
          return eligibleAttempts === 1
            ? json({ detail: "Unavailable" }, 503)
            : json({ items: eligible });
        }
        if (url.pathname.endsWith("/end")) return json({ detail: "Membership end conflict" }, 409);
        if (url.pathname.endsWith("/memberships")) return json({ detail: "Roster conflict" }, 409);
        throw new Error(`Unexpected ${url.pathname}`);
      },
      true,
      true,
      false,
    );
    renderApp("/teams/team-ssg/people");
    expect(
      await screen.findByRole("heading", { name: "Team people could not be loaded" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Eligible Members could not be loaded.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    await user.selectOptions(await screen.findByLabelText(/^Member/), "alan");
    await user.type(
      screen.getByLabelText(/^Reason/),
      "Alan cannot join while a conflicting change is pending.",
    );
    await user.click(screen.getByRole("button", { name: "Add Member" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Roster conflict");
    await user.click(screen.getByRole("button", { name: "Schedule transfer" }));
    await user.selectOptions(screen.getByLabelText(/^Member/), "beth");
    fireEvent.submit(screen.getByRole("button", { name: "Confirm transfer" }).closest("form")!);
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Complete the transfer details"),
    );
    await user.click(screen.getAllByRole("button", { name: "End membership" })[0]);
    await user.type(
      screen.getByLabelText(/Reason for ending/),
      "Lewis cannot leave during a conflicting roster update.",
    );
    await user.click(screen.getByRole("button", { name: "Confirm end" }));
    const endForm = screen.getByRole("button", { name: "Confirm end" }).closest("form")!;
    expect(await within(endForm).findByRole("alert")).toHaveTextContent("Membership end conflict");
  });
});
