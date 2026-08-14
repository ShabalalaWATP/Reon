import { lazy, Suspense } from "react";
import { NavLink, Navigate } from "react-router";

import "../../styles/teams.css";
import "../../styles/board.css";

import { PageState } from "../../components/PageState";
import type { TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import type { Session } from "../../lib/api/types";
import { useAuth } from "../../lib/auth/AuthProvider";
import { StaffQueuePage } from "../work/StaffQueuePage";
import { RoutingRequestRegisters } from "./RoutingRequestRegisters";
import { TeamActivityPanel } from "./TeamActivityPanel";
import { TeamOverviewPage, TeamStatisticsStrip } from "./TeamOverviewPage";
import { TeamPeoplePanel } from "./TeamPeoplePanel";
import {
  useTeamWorkspaceController,
  type TeamWorkspaceState,
  type WorkspaceView,
  type WorkspaceViewLink,
} from "./useTeamWorkspaceController";

const CalendarPage = lazy(() =>
  import("../calendar/CalendarPage").then(({ CalendarPage: page }) => ({ default: page })),
);
const TeamBoardPage = lazy(() =>
  import("../board/TeamBoardPage").then(({ TeamBoardPage: page }) => ({ default: page })),
);

export function TeamWorkspacePage() {
  const { session } = useAuth();
  if (!session) return <PageState kind="error" title="Team workspace could not be loaded" />;
  return <AuthenticatedTeamWorkspace session={session} />;
}

function AuthenticatedTeamWorkspace({ session }: { session: Session }) {
  const state = useTeamWorkspaceController(session);
  if (state.kind === "loading") return <PageState kind="loading" title="Opening team workspace" />;
  if (state.kind === "error") return <Retry onRetry={state.retry} />;
  if (state.kind === "empty")
    return (
      <PageState kind="empty" title="No team workspace assigned">
        Your effective team membership or management authority controls access.
      </PageState>
    );
  if (state.kind === "unavailable")
    return (
      <PageState kind="empty" title="Team workspace unavailable">
        This team is outside your current workspace access.
      </PageState>
    );
  if (state.kind === "redirect") return <Navigate replace to={state.path} />;
  return <WorkspaceReady session={session} state={state} />;
}

function WorkspaceReady({
  session,
  state,
}: {
  session: Session;
  state: Extract<TeamWorkspaceState, { kind: "ready" }>;
}) {
  return (
    <main className="page-stack team-workspace">
      <WorkspaceHeading state={state} />
      <WorkspaceTabs selected={state.selected} views={state.availableViews} />
      <Suspense fallback={<PageState kind="loading" title="Opening team workspace view" />}>
        <WorkspaceContent
          access={state.selected}
          isRouting={state.isRouting}
          userId={session.user.id}
          view={state.view}
        />
      </Suspense>
    </main>
  );
}

function WorkspaceHeading({ state }: { state: Extract<TeamWorkspaceState, { kind: "ready" }> }) {
  const { selected, workspaces } = state;
  return (
    <header className="team-heading">
      <div>
        <span>
          {selected.teamCode} · {selected.workspacePosition?.toLowerCase() ?? "authorised"}
        </span>
        <h1>{selected.teamName}</h1>
        <p>{workspaceDescription(selected)}</p>
      </div>
      {workspaces.length > 1 ? (
        <label className="form-field">
          Workspace
          <select
            onChange={(event) => state.switchWorkspace(event.target.value)}
            value={selected.teamId}
          >
            {workspaces.map((team) => (
              <option key={team.teamId} value={team.teamId}>
                {team.teamName}
              </option>
            ))}
          </select>
        </label>
      ) : null}
    </header>
  );
}

function WorkspaceTabs({
  selected,
  views,
}: {
  selected: TeamWorkspaceAccess;
  views: WorkspaceViewLink[];
}) {
  return (
    <nav aria-label="Organisation workspace views" className="team-tabs">
      {views.map(([key, label]) => (
        <NavLink
          className={({ isActive }) => (isActive ? "team-tab team-tab--active" : "team-tab")}
          key={key}
          to={`/teams/${selected.teamId}/${key}`}
        >
          {label}
        </NavLink>
      ))}
    </nav>
  );
}

function WorkspaceContent({
  access,
  isRouting,
  userId,
  view,
}: {
  access: TeamWorkspaceAccess;
  isRouting: boolean;
  userId: string;
  view: WorkspaceView;
}) {
  switch (view) {
    case "overview":
      return <TeamOverviewPage access={access} userId={userId} />;
    case "people":
      return <TeamPeoplePanel access={access} userId={userId} />;
    case "activity":
      return <TeamActivityPanel teamId={access.teamId} userId={userId} />;
    case "board":
      return <TeamBoardPage access={access} />;
    case "calendar":
      return <CalendarPage access={access} />;
    case "queue":
      return <WorkspaceQueue access={access} isRouting={isRouting} userId={userId} />;
    case "statistics":
      return <WorkspaceStatistics access={access} userId={userId} />;
  }
}

function WorkspaceQueue({
  access,
  isRouting,
  userId,
}: {
  access: TeamWorkspaceAccess;
  isRouting: boolean;
  userId: string;
}) {
  const register = isRouting
    ? (actionRequestIds: ReadonlySet<string>) => (
        <RoutingRequestRegisters
          actionRequestIds={actionRequestIds}
          teamId={access.teamId}
          userId={userId}
        />
      )
    : undefined;
  return (
    <StaffQueuePage
      afterQueue={register}
      description={
        isRouting
          ? "Claim and complete routing decisions currently assigned or available to this unit."
          : "Review and complete work currently assigned or available to this unit."
      }
      embedded
      eyebrow={isRouting ? "Action required" : "Team work"}
      teamId={access.teamId}
      title={isRouting ? "Needs routing action" : "Work queue"}
    />
  );
}

function WorkspaceStatistics({ access, userId }: { access: TeamWorkspaceAccess; userId: string }) {
  return (
    <section className="workspace-statistics">
      <header>
        <span>Authorised unit and descendants</span>
        <h2>Operational statistics</h2>
        <p>
          Measures follow the organisation hierarchy. Sibling and parent branches remain outside
          this workspace.
        </p>
      </header>
      <TeamStatisticsStrip teamId={access.teamId} userId={userId} />
    </section>
  );
}

function Retry({ onRetry }: { onRetry: () => void }) {
  return (
    <PageState
      action={
        <button className="button" onClick={onRetry}>
          Try again
        </button>
      }
      kind="error"
      title="Team workspace could not be loaded"
    >
      Check your connection and current team access.
    </PageState>
  );
}

function workspaceDescription(access: TeamWorkspaceAccess) {
  return access.unitKind === "TEAM" || !access.unitKind
    ? "Team work, assignments, people, availability and performance in one place."
    : "Routing work, people, availability and performance in one place.";
}
