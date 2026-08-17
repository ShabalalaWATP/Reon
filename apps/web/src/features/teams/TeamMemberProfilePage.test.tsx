import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import type { Session } from "../../lib/api/types";
import type { TeamMember, TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import { enabledCapabilities, requesterSession } from "../../test/fixtures";
import { json, mockFeatureFetch, renderApp } from "../../test/render";

const session: Session = {
  ...requesterSession,
  user: {
    ...requesterSession.user,
    id: "analyst-ssg",
    username: "admin11",
    displayName: "Lewis Ferguson",
    role: "DELIVERY_SPECIALIST",
    scope: "SSG Team",
  },
};
const access: TeamWorkspaceAccess = {
  teamId: "team-ssg",
  teamCode: "SSG_TEAM",
  teamName: "SSG Team",
  unitKind: "TEAM",
  workspacePosition: "MEMBER",
  grantId: null,
  permissions: [],
};
const member: TeamMember = {
  membershipId: "membership-ssg",
  accountId: "analyst-ssg",
  displayName: "Lewis Ferguson",
  role: "DELIVERY_SPECIALIST",
  workspacePosition: "MEMBER",
  state: "CURRENT",
  effectiveFrom: "2026-01-01T09:00:00Z",
  effectiveUntil: null,
  version: 1,
  activeWorkCount: 1,
  skills: ["Research", "Data analysis"],
  startReason: null,
  endReason: null,
};

describe("team member profile", () => {
  it("opens a bounded colleague profile and returns to the People register", async () => {
    mockFeatureFetch(
      async (url) => {
        if (url.pathname.endsWith("/auth/me")) return json(session);
        if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
        if (url.pathname.endsWith("/team-workspaces")) return json({ items: [access] });
        if (url.pathname.endsWith("/people/analyst-ssg/profile"))
          return json({
            accountId: "analyst-ssg",
            name: "Lewis Ferguson",
            email: "admin11@mist.example.test?bcc=attacker@example.test",
            role: "DELIVERY_SPECIALIST",
            teamId: access.teamId,
            teamName: access.teamName,
            workspacePosition: "MEMBER",
            membershipState: "CURRENT",
            rankOrGrade: "Analyst",
            skills: member.skills,
            accountActive: true,
          });
        if (url.pathname.endsWith("/people")) return json({ items: [member] });
        throw new Error(`Unexpected ${url.pathname}`);
      },
      true,
      true,
      false,
    );
    const user = userEvent.setup();
    const view = renderApp("/teams/team-ssg/people");

    await user.click(await screen.findByRole("link", { name: "Lewis Ferguson" }));
    expect(await screen.findByRole("heading", { name: "Lewis Ferguson" })).toBeInTheDocument();
    expect(
      screen.getByRole("link", {
        name: "admin11@mist.example.test?bcc=attacker@example.test",
      }),
    ).toHaveAttribute("href", "mailto:admin11%40mist.example.test%3Fbcc%3Dattacker%40example.test");
    expect(screen.getByText("Research, Data analysis")).toBeInTheDocument();
    expect(screen.getByText(/Private profile notes and service numbers/)).toBeInTheDocument();
    const back = screen.getByRole("link", { name: "Back to SSG Team people" });
    expect(back).toHaveAttribute("href", "/teams/team-ssg/people");
    await user.click(back);
    expect(
      await screen.findByRole("table", { name: "Workspace membership history" }),
    ).toBeInTheDocument();
    expect(await axe(view.container)).toHaveNoViolations();
  });

  it("recovers a failed profile read and renders explicit empty and inactive states", async () => {
    let attempts = 0;
    mockFeatureFetch(
      async (url) => {
        if (url.pathname.endsWith("/auth/me")) return json(session);
        if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
        if (url.pathname.endsWith("/team-workspaces")) return json({ items: [access] });
        if (url.pathname.endsWith("/people/analyst-ssg/profile")) {
          attempts += 1;
          if (attempts === 1) return json({ detail: "Unavailable" }, 503);
          return json({
            accountId: "analyst-ssg",
            name: "Lewis Ferguson",
            email: "admin11@mist.example.test",
            role: "DELIVERY_SPECIALIST",
            teamId: access.teamId,
            teamName: access.teamName,
            workspacePosition: "MANAGER",
            membershipState: "ENDED",
            rankOrGrade: null,
            skills: [],
            accountActive: false,
          });
        }
        throw new Error(`Unexpected ${url.pathname}`);
      },
      true,
      true,
      false,
    );
    const user = userEvent.setup();
    renderApp("/teams/team-ssg/people/analyst-ssg");

    expect(
      await screen.findByRole("heading", { name: "Team member profile could not be loaded" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to team people" })).toHaveAttribute(
      "href",
      "/teams/team-ssg/people",
    );
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Inactive account")).toBeInTheDocument();
    expect(screen.getByText("Manager")).toBeInTheDocument();
    expect(screen.getByText("Not provided")).toBeInTheDocument();
    expect(screen.getByText("Not listed")).toBeInTheDocument();
    expect(screen.getByText("Ended")).toBeInTheDocument();
  });
});
