import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import { organisationUnit, organisationUnits, requesterSession } from "../../test/fixtures";
import { json, mockFetch, renderApp } from "../../test/render";
import {
  profileMembershipText,
  profilePositionLabel,
  profileWorkspacePositionText,
} from "./profileModel";

const personalProfile = {
  email: "admin2@istari.example.test",
  profileTeam: null,
  rankOrGrade: null,
  serviceNumber: null,
  skills: [],
  additionalInformation: null,
  version: 1,
};

describe("personal profile", () => {
  it("describes every organisation-assignment state", () => {
    expect(profileMembershipText(1, [], true)).toBe("Organisation assignments unavailable");
    expect(profileMembershipText(0, [], false)).toBe("No organisation unit assignment required");
    expect(profileMembershipText(1, [], false)).toBe("Loading organisation assignments…");
    expect(profileMembershipText(2, ["SSG Team", "Cedar Team"], false)).toBe(
      "SSG Team, Cedar Team",
    );
  });

  it("describes every workspace-position state", () => {
    const manager = {
      teamId: "crioc",
      teamCode: "CRIOC",
      teamName: "CRIOC",
      workspacePosition: "MANAGER" as const,
      grantId: null,
      permissions: [],
    };
    const member = {
      ...manager,
      teamId: "jock",
      teamCode: "JOCK",
      teamName: "JOCK",
      workspacePosition: "MEMBER" as const,
    };
    const legacy = {
      ...member,
      teamId: "sygoc",
      teamCode: "SYGOC",
      teamName: "SYGOC",
      workspacePosition: undefined,
    };

    expect(profilePositionLabel([])).toBeNull();
    expect(profilePositionLabel([manager])).toBe("Manager");
    expect(profilePositionLabel([manager, member])).toBe("Mixed positions");
    expect(profileWorkspacePositionText(1, [], true)).toBe("Workspace positions unavailable");
    expect(profileWorkspacePositionText(0, [], false)).toBe("No workspace position required");
    expect(profileWorkspacePositionText(1, [], false)).toBe("Loading workspace positions…");
    expect(profileWorkspacePositionText(3, [manager, member, legacy], false)).toBe(
      "Manager in CRIOC; Member in JOCK; Member in SYGOC",
    );
  });

  it("gives a Customer a current profile without internal routing scope", async () => {
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/profile")) return json(personalProfile);
      throw new Error(`Unexpected ${url.pathname}`);
    });

    const view = renderApp("/profile");
    expect(await screen.findByRole("heading", { name: "John McGinn" })).toBeInTheDocument();
    expect(screen.getByText("admin2")).toBeInTheDocument();
    expect(screen.getByText("Own requests and released products")).toBeInTheDocument();
    expect(screen.getByText("Personal Customer workspace")).toBeInTheDocument();
    expect(screen.queryByText(/Requesting Area/u)).not.toBeInTheDocument();
    expect(await axe(view.container)).toHaveNoViolations();
  });

  it("shows a staff member's current organisation assignments", async () => {
    const ssg = organisationUnit("SSG_TEAM");
    const manager = {
      ...requesterSession,
      user: {
        ...requesterSession.user,
        id: "manager-ssg",
        username: "admin8",
        displayName: "Grant Hanley",
        role: "DELIVERY_TEAM_LEAD" as const,
        scope: "SSG Team",
        organisationUnitIds: [ssg.id],
      },
    };
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(manager);
      if (url.pathname.endsWith("/profile")) return json(personalProfile);
      if (url.pathname.endsWith("/organisation/units")) return json({ items: organisationUnits });
      throw new Error(`Unexpected ${url.pathname}`);
    });

    renderApp("/profile");
    expect(await screen.findByRole("heading", { name: "Grant Hanley" })).toBeInTheDocument();
    expect(screen.getAllByText("SSG Team").length).toBeGreaterThan(0);
    expect(screen.getByText("Team management")).toBeInTheDocument();
  });

  it("distinguishes a representative routing role from Manager authority", async () => {
    const crioc = organisationUnit("CRIOC");
    const manager = {
      ...requesterSession,
      user: {
        ...requesterSession.user,
        id: "manager-crioc",
        username: "admin74",
        displayName: "Alan Rough",
        role: "INTAKE_TRIAGE" as const,
        scope: "CRIOC",
        organisationUnitIds: [crioc.id],
      },
    };
    mockFetch(
      (url) => {
        if (url.pathname.endsWith("/auth/me")) return json(manager);
        if (url.pathname.endsWith("/profile")) return json(personalProfile);
        if (url.pathname.endsWith("/organisation/units")) return json({ items: organisationUnits });
        if (url.pathname.endsWith("/team-workspaces"))
          return json({
            items: [
              {
                teamId: crioc.id,
                teamCode: "CRIOC",
                teamName: "CRIOC",
                unitKind: "ROOT",
                workspacePosition: "MANAGER",
                grantId: "crioc-roster-grant",
                permissions: ["ROSTER"],
              },
            ],
          });
        throw new Error(`Unexpected ${url.pathname}`);
      },
      true,
      true,
      false,
    );

    renderApp("/profile");
    expect(await screen.findByRole("heading", { name: "Alan Rough" })).toBeInTheDocument();
    expect(await screen.findByText("CRIOC Routing User · Manager")).toBeInTheDocument();
    expect(await screen.findByText("Manager in CRIOC")).toBeInTheDocument();
    expect(
      await screen.findByText("CRIOC routing; Manager controls for CRIOC"),
    ).toBeInTheDocument();
  });

  it("makes loading and unavailable staff assignments explicit", async () => {
    const ssg = organisationUnit("SSG_TEAM");
    const manager = {
      ...requesterSession,
      user: {
        ...requesterSession.user,
        role: "DELIVERY_TEAM_LEAD" as const,
        organisationUnitIds: [ssg.id],
      },
    };
    let resolveOrganisation: (response: Response) => void = () => undefined;
    const organisationResponse = new Promise<Response>((resolve) => {
      resolveOrganisation = resolve;
    });
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(manager);
      if (url.pathname.endsWith("/profile")) return json(personalProfile);
      if (url.pathname.endsWith("/organisation/units")) return organisationResponse;
      throw new Error(`Unexpected ${url.pathname}`);
    });

    renderApp("/profile");
    expect(await screen.findByText("Loading organisation assignments…")).toBeInTheDocument();
    await act(async () => resolveOrganisation(json({ detail: "Unavailable" }, 503)));
    expect(await screen.findByText("Organisation assignments unavailable")).toBeInTheDocument();
  });

  it("lets the account holder maintain optional personal details", async () => {
    let savedBody: Record<string, unknown> | undefined;
    mockFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/profile") && init.method === "PATCH") {
        savedBody = JSON.parse(String(init.body)) as Record<string, unknown>;
        return json({
          profileTeam: "Fictional Customer Team",
          rankOrGrade: "Grade 7",
          serviceNumber: "SYN-1042",
          skills: ["Research", "Data analysis"],
          additionalInformation: "Synthetic profile context.",
          version: 2,
        });
      }
      if (url.pathname.endsWith("/profile")) return json(personalProfile);
      throw new Error(`Unexpected ${url.pathname}`);
    });

    const user = userEvent.setup();
    renderApp("/profile");
    await user.type(
      await screen.findByLabelText(/Team or business area/),
      "Fictional Customer Team",
    );
    await user.type(screen.getByLabelText(/Rank or grade/), "Grade 7");
    await user.type(screen.getByLabelText(/Service number/), "SYN-1042");
    await user.type(screen.getByLabelText(/Operational skills/), "Research, Data analysis");
    await user.type(screen.getByLabelText(/Additional information/), "Synthetic profile context.");
    await user.click(screen.getByRole("button", { name: "Save personal details" }));

    await waitFor(() =>
      expect(savedBody).toEqual({
        profileTeam: "Fictional Customer Team",
        rankOrGrade: "Grade 7",
        serviceNumber: "SYN-1042",
        skills: ["Research", "Data analysis"],
        additionalInformation: "Synthetic profile context.",
        expectedVersion: 1,
      }),
    );
    expect(screen.getByRole("status")).toHaveTextContent("Personal details saved");

    expect(
      await screen.findByRole("button", { name: "Edit personal details" }),
    ).toBeInTheDocument();
    expect(screen.getByText("SYN-1042")).toBeInTheDocument();
    expect(screen.getByText("Data analysis")).toBeInTheDocument();
    expect(screen.queryByLabelText(/Team or business area/)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Edit personal details" }));
    expect(await screen.findByLabelText(/Rank or grade/)).toHaveValue("Grade 7");
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByLabelText(/Rank or grade/)).not.toBeInTheDocument();
    expect(screen.getByText("Grade 7")).toBeInTheDocument();
  });

  it("presents saved personal details as page content until Edit is chosen", async () => {
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/profile"))
        return json({
          ...personalProfile,
          profileTeam: "Synthetic Customer Team",
          skills: ["Research"],
        });
      throw new Error(`Unexpected ${url.pathname}`);
    });

    const user = userEvent.setup();
    renderApp("/profile");
    expect(await screen.findByText("Synthetic Customer Team")).toBeInTheDocument();
    expect(screen.getByText("Research")).toBeInTheDocument();
    expect(screen.getAllByText("Not provided")).toHaveLength(3);
    expect(screen.queryByLabelText(/Service number/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Edit personal details" }));
    expect(await screen.findByLabelText(/Team or business area/)).toHaveValue(
      "Synthetic Customer Team",
    );
  });

  it("sends blank optional fields as null and reports a save conflict", async () => {
    let savedBody: Record<string, unknown> | undefined;
    mockFetch((url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/profile") && init.method === "PATCH") {
        savedBody = JSON.parse(String(init.body)) as Record<string, unknown>;
        return json({ detail: "Profile changed elsewhere" }, 409);
      }
      if (url.pathname.endsWith("/profile")) return json(personalProfile);
      throw new Error(`Unexpected ${url.pathname}`);
    });

    const user = userEvent.setup();
    renderApp("/profile");
    await user.type(await screen.findByLabelText(/Rank or grade/), "Grade 6");
    await user.click(screen.getByRole("button", { name: "Save personal details" }));

    await waitFor(() =>
      expect(savedBody).toEqual({
        profileTeam: null,
        rankOrGrade: "Grade 6",
        serviceNumber: null,
        skills: [],
        additionalInformation: null,
        expectedVersion: 1,
      }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /personal details could not be saved/i,
    );
  });

  it("keeps every personal detail within its documented boundary", async () => {
    mockFetch((url) => {
      if (url.pathname.endsWith("/auth/me")) return json(requesterSession);
      if (url.pathname.endsWith("/profile")) return json(personalProfile);
      throw new Error(`Unexpected ${url.pathname}`);
    });

    renderApp("/profile");
    fireEvent.change(await screen.findByLabelText(/Team or business area/), {
      target: { value: "T".repeat(121) },
    });
    fireEvent.change(screen.getByLabelText(/Rank or grade/), {
      target: { value: "R".repeat(121) },
    });
    fireEvent.change(screen.getByLabelText(/Service number/), {
      target: { value: "S".repeat(81) },
    });
    fireEvent.change(screen.getByLabelText(/Additional information/), {
      target: { value: "I".repeat(2001) },
    });
    fireEvent.change(screen.getByLabelText(/Operational skills/), {
      target: { value: Array.from({ length: 13 }, (_, index) => `Skill ${index}`).join(", ") },
    });

    expect(await screen.findAllByRole("alert")).toHaveLength(5);
    expect(screen.getByRole("button", { name: "Save personal details" })).toBeDisabled();
  });
});
