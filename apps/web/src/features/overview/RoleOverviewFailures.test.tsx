import { screen } from "@testing-library/react";
import { expect, it } from "vitest";

import { enabledCapabilities, staffSession } from "../../test/fixtures";
import { json, mockFeatureFetch, renderApp } from "../../test/render";

const qcSession = {
  ...staffSession,
  user: { ...staffSession.user, id: "qc-failure-user", role: "QUALITY_RELEASE" as const },
};
const scope = { id: "qc-scope", unitId: "qc-unit", name: "Combined QC Team" };
const actions = {
  items: [],
  counts: { needsMyAction: 0, waiting: 0, dueSoon: 0, recentlyCompleted: 0 },
  savedViews: [],
  nextCursor: null,
  freshness: {
    status: "CURRENT",
    projectedAt: null,
    sourceChangedAt: null,
    lagSeconds: null,
    pendingCount: 0,
  },
};
const statistics = { summary: [] };

it.each(["/me/actions", "/statistics/scopes", "/statistics"])(
  "reports a failed QC overview dependency at %s",
  async (failedPath) => {
    mockFeatureFetch(
      (url) => {
        if (url.pathname.endsWith("/auth/me")) return json(qcSession);
        if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
        if (url.pathname.endsWith(failedPath)) return json({ detail: "Unavailable" }, 503);
        if (url.pathname.endsWith("/me/actions")) return json(actions);
        if (url.pathname.endsWith("/team-workspaces"))
          return json({
            items: [
              {
                teamId: "qc-unit",
                teamCode: "QC_TEAM",
                teamName: "Combined QC Team",
                workspacePosition: "MANAGER",
                grantId: "grant-qc",
                permissions: ["STATISTICS"],
              },
            ],
          });
        if (url.pathname.endsWith("/statistics/scopes")) return json({ items: [scope] });
        if (url.pathname.endsWith("/statistics")) return json(statistics);
        throw new Error(`Unexpected ${url.pathname}`);
      },
      true,
      false,
      false,
      false,
      true,
    );
    renderApp("/overview");

    expect(
      await screen.findByRole("heading", { name: "Quality overview could not be loaded" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "QC Team workload" })).not.toBeInTheDocument();
  },
);
