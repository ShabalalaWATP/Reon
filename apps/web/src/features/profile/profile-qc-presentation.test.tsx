import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { organisationUnit, requesterSession } from "../../test/fixtures";
import { json, mockFetch, renderApp } from "../../test/render";

const personalProfile = {
  email: "admin85@mist.example.test",
  profileTeam: null,
  rankOrGrade: null,
  serviceNumber: null,
  skills: [],
  additionalInformation: null,
  version: 1,
};

describe("QC profile presentation", () => {
  it("does not grant a QC User dissemination authority in profile copy", async () => {
    const qcUnit = organisationUnit("CRIOC");
    const qcUser = {
      ...requesterSession,
      activeContext: "STAFF" as const,
      availableContexts: ["STAFF" as const],
      user: {
        ...requesterSession.user,
        id: "qc-user",
        username: "admin85",
        displayName: "Synthetic QC User",
        role: "QUALITY_RELEASE" as const,
        scope: "Combined QC Team",
        organisationUnitIds: [qcUnit.id],
      },
    };
    mockFetch(
      (url) => {
        if (url.pathname.endsWith("/auth/me")) return json(qcUser);
        if (url.pathname.endsWith("/profile")) return json(personalProfile);
        if (url.pathname.endsWith("/organisation/units")) return json({ items: [qcUnit] });
        if (url.pathname.endsWith("/team-workspaces"))
          return json({
            items: [
              {
                teamId: qcUnit.id,
                teamCode: qcUnit.code,
                teamName: "Combined QC Team",
                workspacePosition: "MEMBER",
                grantId: "qc-member-grant",
                permissions: [],
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
    expect(await screen.findByRole("heading", { name: "Synthetic QC User" })).toBeInTheDocument();
    expect(screen.getByText("QC User")).toBeInTheDocument();
    expect(screen.getByText("Quality control")).toBeInTheDocument();
    expect(screen.getByText("Completes quality checks on product packages.")).toBeInTheDocument();
    expect(
      screen.queryByText(/releases products|dissemination authority/iu),
    ).not.toBeInTheDocument();
  });
});
