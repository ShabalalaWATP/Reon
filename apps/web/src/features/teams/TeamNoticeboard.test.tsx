import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import type { Session } from "../../lib/api/types";
import type { TeamWorkspaceAccess, WorkspaceRecord } from "../../lib/api/teamTypes";
import { json, mockFeatureFetch, renderApp } from "../../test/render";
import { enabledCapabilities, requesterSession } from "../../test/fixtures";

const managerSession: Session = {
  ...requesterSession,
  user: {
    ...requesterSession.user,
    id: "manager-ssg",
    username: "admin8",
    displayName: "Grant Hanley",
    role: "DELIVERY_TEAM_LEAD",
    scope: "SSG Team",
  },
};
const analystSession: Session = {
  ...managerSession,
  user: {
    ...managerSession.user,
    id: "analyst-ssg",
    username: "admin11",
    displayName: "Lewis Ferguson",
    role: "DELIVERY_SPECIALIST",
  },
};
const managerAccess: TeamWorkspaceAccess = {
  teamId: "team-ssg",
  teamCode: "SSG_TEAM",
  teamName: "SSG Team",
  unitKind: "TEAM",
  workspacePosition: "MANAGER",
  grantId: "grant-ssg",
  permissions: ["BOARD", "CALENDAR", "CAPACITY", "ROSTER", "STATISTICS"],
  views: ["OVERVIEW", "BOARD", "CALENDAR", "PEOPLE", "STATISTICS", "ACTIVITY"],
};
const analystAccess: TeamWorkspaceAccess = {
  ...managerAccess,
  workspacePosition: "MEMBER",
  grantId: null,
  permissions: [],
};

function record(overrides: Partial<WorkspaceRecord>): WorkspaceRecord {
  return {
    id: "record-note",
    kind: "HANDOVER",
    status: "OPEN",
    title: "Shift handover expectations",
    body: "Synthetic standing notice detail.",
    url: null,
    createdByDisplayName: "Grant Hanley",
    resolution: null,
    version: 2,
    createdAt: "2026-08-10T09:00:00Z",
    updatedAt: "2026-08-12T09:00:00Z",
    ...overrides,
  };
}

const seededRecords = [
  record({}),
  record({
    id: "record-link",
    kind: "LINK",
    title: "Team reference library",
    body: "Synthetic shared reference.",
    url: "https://example.test/library",
    version: 1,
    updatedAt: "2026-08-11T09:00:00Z",
  }),
  record({
    id: "record-closed",
    status: "RESOLVED",
    title: "Superseded notice",
    resolution: "Replaced by the current notice.",
  }),
];

type RecordedCall = { path: string; body: Record<string, unknown> };

function mockOverview(
  session: Session,
  access: TeamWorkspaceAccess,
  calls: RecordedCall[],
  options: { empty?: boolean; mutationFailure?: boolean; recordsFailure?: boolean } = {},
) {
  let items = options.empty ? [] : [...seededRecords];
  return mockFeatureFetch(
    async (url, init) => {
      if (url.pathname.endsWith("/auth/me")) return json(session);
      if (url.pathname.endsWith("/me/capabilities")) return json(enabledCapabilities);
      if (url.pathname.endsWith("/team-workspaces")) return json({ items: [access] });
      if (url.pathname.endsWith("/people")) return json({ items: [] });
      if (url.pathname.endsWith("/activity")) return json({ items: [] });
      if (url.pathname.endsWith("/calendar")) return json({ items: [] });
      if (url.pathname.endsWith("/board"))
        return json({
          items: [],
          nextCursor: null,
          columnCounts: {},
          totalCount: 0,
          wipLimits: {},
          configurationVersion: 0,
          savedViews: [],
          generatedAt: "2026-08-13T09:00:00Z",
        });
      if (url.pathname.endsWith("/records") && init.method === "POST") {
        if (options.mutationFailure) return json({ detail: "Synthetic failure" }, 503);
        const body = JSON.parse(String(init.body)) as Record<string, unknown>;
        calls.push({ path: url.pathname, body });
        items = [
          ...items,
          record({
            id: `record-${items.length}`,
            kind: body.kind as WorkspaceRecord["kind"],
            title: String(body.title),
            body: String(body.body),
            url: (body.url as string | undefined) ?? null,
            updatedAt: "2026-08-13T10:00:00Z",
          }),
        ];
        return json({ items });
      }
      if (url.pathname.endsWith("/resolve") && init.method === "POST") {
        if (options.mutationFailure) return json({ detail: "Synthetic failure" }, 503);
        const body = JSON.parse(String(init.body)) as Record<string, unknown>;
        calls.push({ path: url.pathname, body });
        items = items.filter((value) => !url.pathname.includes(value.id));
        return json({ items });
      }
      if (url.pathname.endsWith("/records"))
        return options.recordsFailure ? json({ detail: "Unavailable" }, 503) : json({ items });
      if (url.pathname.endsWith(`/team-workspaces/${access.teamId}`))
        return json({
          access,
          managerCount: 2,
          analystCount: 5,
          activeWorkCount: 1,
          dueSoonCount: 0,
          overdueCount: 0,
        });
      throw new Error(`Unexpected ${url.pathname}`);
    },
    true,
    true,
    false,
  );
}

describe("team noticeboard and pinned links", () => {
  it("lets a Manager read, post, pin and archive shared workspace records", async () => {
    const calls: RecordedCall[] = [];
    mockOverview(managerSession, managerAccess, calls);
    const user = userEvent.setup();
    const view = renderApp("/teams/team-ssg/overview");

    expect(
      await screen.findByRole("heading", { name: "Noticeboard and pinned links" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("Shift handover expectations")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Team reference library" })).toHaveAttribute(
      "href",
      "https://example.test/library",
    );
    expect(screen.queryByText("Superseded notice")).not.toBeInTheDocument();
    expect(await axe(view.container)).toHaveNoViolations();

    await user.click(screen.getByRole("button", { name: "Post a notice" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByRole("button", { name: "Post a notice" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Post a notice" }));
    await user.type(screen.getByLabelText(/^Notice title/), "Watchkeeper rotation");
    await user.type(
      screen.getByLabelText(/^Notice detail/),
      "The synthetic rotation starts on Monday.",
    );
    await user.click(screen.getByRole("button", { name: "Post notice" }));
    expect(await screen.findByText("Watchkeeper rotation")).toBeInTheDocument();
    expect(calls.at(-1)?.body).toMatchObject({
      grantId: "grant-ssg",
      kind: "HANDOVER",
      title: "Watchkeeper rotation",
    });

    await user.click(screen.getByRole("button", { name: "Add a link" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByRole("button", { name: "Add a link" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Add a link" }));
    await user.type(screen.getByLabelText(/^Link title/), "Style guide");
    await user.type(screen.getByLabelText(/^Link URL/), "https://example.test/style");
    await user.type(screen.getByLabelText(/^Short description/), "Synthetic writing guidance.");
    await user.click(screen.getByRole("button", { name: "Add link" }));
    expect(await screen.findByRole("link", { name: "Style guide" })).toBeInTheDocument();
    expect(calls.at(-1)?.body).toMatchObject({ kind: "LINK", url: "https://example.test/style" });

    await user.click(screen.getByRole("button", { name: "Archive Shift handover expectations" }));
    await user.click(screen.getByRole("button", { name: "Keep" }));
    expect(
      screen.getByRole("button", { name: "Archive Shift handover expectations" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Archive Shift handover expectations" }));
    const archiveForm = screen.getByRole("button", { name: "Confirm archive" }).closest("form")!;
    await user.type(
      within(archiveForm).getByLabelText(/^Reason/),
      "This notice has been replaced by the rotation notice.",
    );
    await user.click(screen.getByRole("button", { name: "Confirm archive" }));
    await waitFor(() =>
      expect(screen.queryByText("Shift handover expectations")).not.toBeInTheDocument(),
    );
    expect(calls.at(-1)?.path).toContain("/records/record-note/resolve");
    expect(calls.at(-1)?.body).toMatchObject({ grantId: "grant-ssg", expectedVersion: 2 });
  });

  it("keeps the noticeboard read-only without a Manager grant", async () => {
    mockOverview(analystSession, analystAccess, []);
    renderApp("/teams/team-ssg/overview");
    expect(await screen.findByText("Shift handover expectations")).toBeInTheDocument();
    expect(screen.getByText(/kept current by this workspace's Managers/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Post a notice" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add a link" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Archive / })).not.toBeInTheDocument();
  });

  it("reports an unavailable noticeboard without hiding the rest of the overview", async () => {
    mockOverview(managerSession, managerAccess, [], { recordsFailure: true });
    renderApp("/teams/team-ssg/overview");
    expect(await screen.findByText("Noticeboard unavailable")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Team attention" })).toBeInTheDocument();
  });

  it("shows empty columns and reports failed Manager changes", async () => {
    mockOverview(managerSession, managerAccess, [], { empty: true });
    const user = userEvent.setup();
    const first = renderApp("/teams/team-ssg/overview");
    expect(await screen.findByText("No standing notices.")).toBeInTheDocument();
    expect(screen.getByText("No pinned links.")).toBeInTheDocument();
    first.unmount();

    mockOverview(managerSession, managerAccess, [], { mutationFailure: true });
    renderApp("/teams/team-ssg/overview");
    await screen.findByText("Shift handover expectations");
    await user.click(screen.getByRole("button", { name: "Post a notice" }));
    await user.type(screen.getByLabelText(/^Notice title/), "Failed notice");
    await user.type(screen.getByLabelText(/^Notice detail/), "Synthetic failure detail.");
    await user.click(screen.getByRole("button", { name: "Post notice" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Synthetic failure");
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    await user.click(screen.getByRole("button", { name: "Add a link" }));
    await user.type(screen.getByLabelText(/^Link title/), "Failed link");
    await user.type(screen.getByLabelText(/^Link URL/), "https://example.test/fail");
    await user.type(screen.getByLabelText(/^Short description/), "Synthetic failure detail.");
    await user.click(screen.getByRole("button", { name: "Add link" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Synthetic failure");
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    await user.click(screen.getByRole("button", { name: "Archive Shift handover expectations" }));
    const archiveForm = screen.getByRole("button", { name: "Confirm archive" }).closest("form")!;
    await user.type(within(archiveForm).getByLabelText(/^Reason/), "Synthetic archive failure.");
    await user.click(screen.getByRole("button", { name: "Confirm archive" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Synthetic failure");
  });
});
