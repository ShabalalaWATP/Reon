import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { NavLink, Navigate, useNavigate, useParams } from "react-router";

import "../../styles/teams.css";
import "../../styles/board.css";

import { PageState } from "../../components/PageState";
import { api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import { useAuth } from "../../lib/auth/AuthProvider";
import { StaffQueuePage } from "../work/StaffQueuePage";
import { TeamActivityPanel } from "./TeamActivityPanel";
import { TeamOverviewPage, TeamStatisticsStrip } from "./TeamOverviewPage";
import { TeamPeoplePanel } from "./TeamPeoplePanel";
import { RoutingRequestRegisters } from "./RoutingRequestRegisters";

const CalendarPage = lazy(() => import("../calendar/CalendarPage")
  .then(({ CalendarPage: page }) => ({ default: page })));
const TeamBoardPage = lazy(() => import("../board/TeamBoardPage")
  .then(({ TeamBoardPage: page }) => ({ default: page })));
const deliveryViews = [
  ["overview", "Overview"],
  ["queue", "Work queue"],
  ["board", "Board"],
  ["calendar", "Calendar"],
  ["people", "People"],
  ["statistics", "Statistics"],
  ["activity", "Activity"],
] as const;
const routingViews = [
  ["overview", "Overview"],
  ["queue", "Work queue"],
  ["calendar", "Calendar"],
  ["people", "People"],
  ["statistics", "Statistics"],
  ["activity", "Activity"],
] as const;
export function TeamWorkspacePage() {
  const { session } = useAuth();
  const navigate = useNavigate();
  const { teamId, view = "overview" } = useParams();
  const userId = session!.user.id;
  const workspaces = useQuery({
    queryKey: protectedQueryKeys.teamWorkspaces(userId),
    queryFn: api.teamWorkspaces,
  });
  if (workspaces.isPending) {
    return <PageState kind="loading" title="Opening team workspace" />;
  }
  if (workspaces.isError) {
    return <Retry onRetry={() => void workspaces.refetch()} />;
  }
  if (workspaces.data.items.length === 0) {
    return <PageState kind="empty" title="No team workspace assigned">Your effective team membership or management authority controls access.</PageState>;
  }
  const selected = workspaces.data.items.find((item) => item.teamId === teamId);
  if (!selected) {
    return <PageState kind="empty" title="Team workspace unavailable">This team is outside your current workspace access.</PageState>;
  }
  const baseViews = selected.unitKind && selected.unitKind !== "TEAM" ? routingViews : deliveryViews;
  const isRoutingWorkspace = selected.unitKind !== undefined && selected.unitKind !== "TEAM";
  const availableViews = baseViews.filter(([key]) => key === "queue" || !selected.views || selected.views.includes(key.toUpperCase()));
  if (!availableViews.some(([key]) => key === view)) {
    return <Navigate replace to={`/teams/${selected.teamId}/overview`} />;
  }
  return (
    <main className="page-stack team-workspace">
      <header className="team-heading">
        <div><span>{selected.teamCode} · {selected.workspacePosition?.toLowerCase() ?? "authorised"}</span><h1>{selected.teamName}</h1><p>{selected.unitKind === "TEAM" || !selected.unitKind ? "Team work, assignments, people, availability and performance in one place." : "Routing work, people, availability and performance in one place."}</p></div>
        {workspaces.data.items.length > 1 ? (
          <label className="form-field">Workspace
            <select onChange={(event) => { void navigate(`/teams/${event.target.value}/overview`); }} value={selected.teamId}>
              {workspaces.data.items.map((team) => <option key={team.teamId} value={team.teamId}>{team.teamName}</option>)}
            </select>
          </label>
        ) : null}
      </header>
      <nav aria-label="Organisation workspace views" className="team-tabs">
        {availableViews.map(([key, label]) => <NavLink className={({ isActive }) => isActive ? "team-tab team-tab--active" : "team-tab"} key={key} to={`/teams/${selected.teamId}/${key}`}>{label}</NavLink>)}
      </nav>
      <Suspense fallback={<PageState kind="loading" title="Opening team workspace view" />}>
        {view === "overview" ? <TeamOverviewPage access={selected} userId={userId} /> : null}
        {view === "people" ? <TeamPeoplePanel access={selected} userId={userId} /> : null}
        {view === "activity" ? <TeamActivityPanel teamId={selected.teamId} userId={userId} /> : null}
        {view === "board" ? <TeamBoardPage access={selected} /> : null}
        {view === "calendar" ? <CalendarPage access={selected} /> : null}
        {view === "queue" ? <StaffQueuePage afterQueue={isRoutingWorkspace ? (actionRequestIds) => <RoutingRequestRegisters actionRequestIds={actionRequestIds} teamId={selected.teamId} userId={userId} /> : undefined} description={isRoutingWorkspace ? "Claim and complete routing decisions currently assigned or available to this unit." : "Review and complete work currently assigned or available to this unit."} embedded eyebrow={isRoutingWorkspace ? "Action required" : "Team work"} teamId={selected.teamId} title={isRoutingWorkspace ? "Needs routing action" : "Work queue"} /> : null}
        {view === "statistics" ? <WorkspaceStatistics access={selected} userId={userId} /> : null}
      </Suspense>
    </main>
  );
}

function WorkspaceStatistics({ access, userId }: { access: import("../../lib/api/teamTypes").TeamWorkspaceAccess; userId: string }) {
  return <section className="workspace-statistics"><header><span>Authorised unit and descendants</span><h2>Operational statistics</h2><p>Measures follow the organisation hierarchy. Sibling and parent branches remain outside this workspace.</p></header><TeamStatisticsStrip teamId={access.teamId} userId={userId} /></section>;
}

function Retry({ onRetry }: { onRetry: () => void }) {
  return <PageState action={<button className="button" onClick={onRetry}>Try again</button>} kind="error" title="Team workspace could not be loaded">Check your connection and current team access.</PageState>;
}
