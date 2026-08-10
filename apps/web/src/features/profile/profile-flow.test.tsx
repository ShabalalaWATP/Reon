import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import { organisationUnit, organisationUnits, requesterSession } from "../../test/fixtures";
import { json, mockFetch, renderApp } from "../../test/render";
import { profileMembershipText } from "./profileModel";

const personalProfile = {
  email: "admin2@istari.example.test",
  profileTeam: null,
  rankOrGrade: null,
  serviceNumber: null,
  additionalInformation: null,
  version: 1,
};

describe("personal profile", () => {
  it("describes every organisation-assignment state", () => {
    expect(profileMembershipText(1, [], true)).toBe("Organisation assignments unavailable");
    expect(profileMembershipText(0, [], false)).toBe("No organisation unit assignment required");
    expect(profileMembershipText(1, [], false)).toBe("Loading organisation assignments…");
    expect(profileMembershipText(2, ["OSG Team", "Cedar Team"], false)).toBe("OSG Team, Cedar Team");
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
    const osg = organisationUnit("OSG_TEAM");
    const manager = {
      ...requesterSession,
      user: {
        ...requesterSession.user,
        id: "manager-osg",
        username: "admin8",
        displayName: "Grant Hanley",
        role: "DELIVERY_TEAM_LEAD" as const,
        scope: "OSG Team",
        organisationUnitIds: [osg.id],
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
    expect(screen.getAllByText("OSG Team").length).toBeGreaterThan(0);
    expect(screen.getByText("Team management")).toBeInTheDocument();
  });

  it("makes loading and unavailable staff assignments explicit", async () => {
    const osg = organisationUnit("OSG_TEAM");
    const manager = {
      ...requesterSession,
      user: {
        ...requesterSession.user,
        role: "DELIVERY_TEAM_LEAD" as const,
        organisationUnitIds: [osg.id],
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
          additionalInformation: "Synthetic profile context.",
          version: 2,
        });
      }
      if (url.pathname.endsWith("/profile")) return json(personalProfile);
      throw new Error(`Unexpected ${url.pathname}`);
    });

    const user = userEvent.setup();
    renderApp("/profile");
    await user.type(await screen.findByLabelText(/Team or business area/), "Fictional Customer Team");
    await user.type(screen.getByLabelText(/Rank or grade/), "Grade 7");
    await user.type(screen.getByLabelText(/Service number/), "SYN-1042");
    await user.type(screen.getByLabelText(/Additional information/), "Synthetic profile context.");
    await user.click(screen.getByRole("button", { name: "Save personal details" }));

    await waitFor(() => expect(savedBody).toEqual({
      profileTeam: "Fictional Customer Team",
      rankOrGrade: "Grade 7",
      serviceNumber: "SYN-1042",
      additionalInformation: "Synthetic profile context.",
      expectedVersion: 1,
    }));
    expect(screen.getByRole("status")).toHaveTextContent("Personal details saved");
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

    await waitFor(() => expect(savedBody).toEqual({
      profileTeam: null,
      rankOrGrade: "Grade 6",
      serviceNumber: null,
      additionalInformation: null,
      expectedVersion: 1,
    }));
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

    expect(await screen.findAllByRole("alert")).toHaveLength(4);
    expect(screen.getByRole("button", { name: "Save personal details" })).toBeDisabled();
  });
});
