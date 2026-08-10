import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { Link, NavLink, Navigate, useNavigate, useParams } from "react-router";

import { PageState } from "../../components/PageState";
import { api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import { useAuth } from "../../lib/auth/AuthProvider";
import { useCapabilities } from "../../lib/capabilities/useCapabilities";
import { addLocalDays, localDateInputValue } from "../../lib/dateInputs";
import { TeamActivityPanel } from "./TeamActivityPanel";
import { TeamPeoplePanel } from "./TeamPeoplePanel";
import { RoutingQueuePanel } from "./RoutingQueuePanel";
import { WorkspaceCollaborationPanel } from "./WorkspaceCollaborationPanel";

const CalendarPage = lazy(() => import("../calendar/CalendarPage")
  .then(({ CalendarPage: page }) => ({ default: page })));
const TeamBoardPage = lazy(() => import("../board/TeamBoardPage")
  .then(({ TeamBoardPage: page }) => ({ default: page })));
const TeamPlanningPage = lazy(() => import("../board/TeamPlanningPage")
  .then(({ TeamPlanningPage: page }) => ({ default: page })));

const deliveryViews = [
  ["overview", "Overview"],
  ["board", "Board"],
  ["calendar", "Calendar"],
  ["people", "People"],
  ["planning", "Planning"],
  ["statistics", "Statistics"],
  ["activity", "Activity"],
] as const;
const routingViews = [
  ["overview", "Overview"],
  ["queue", "Queue"],
  ["calendar", "Calendar"],
  ["people", "People"],
  ["statistics", "Statistics"],
  ["handover", "Handover"],
  ["activity", "Activity"],
] as const;
const overviewTo = localDateInputValue(new Date());
const overviewFrom = localDateInputValue(addLocalDays(new Date(), -29));

export function TeamWorkspacePage() {
  const { session } = useAuth();
  const { capabilities, isPending: capabilitiesPending } = useCapabilities();
  const navigate = useNavigate();
  const { teamId, view = "overview" } = useParams();
  const userId = session?.user.id ?? "anonymous";
  const workspaces = useQuery({
    queryKey: protectedQueryKeys.teamWorkspaces(userId),
    queryFn: api.teamWorkspaces,
    enabled: Boolean(session),
  });
  if (capabilitiesPending || workspaces.isPending) {
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
  const availableViews = baseViews.filter(([key]) => (key !== "planning" || capabilities.planning) && (!selected.views || selected.views.includes(key.toUpperCase())));
  if (!availableViews.some(([key]) => key === view)) {
    return <Navigate replace to={`/teams/${selected.teamId}/overview`} />;
  }
  return (
    <main className="page-stack team-workspace">
      <header className="team-heading">
        <div><span>{selected.teamCode} · {selected.workspacePosition?.toLowerCase() ?? "authorised"}</span><h1>{selected.teamName}</h1><p>{selected.unitKind === "TEAM" || !selected.unitKind ? "Shared delivery workspace for staffing, service work and team planning." : "Shared routing workspace for queue decisions, people, calendar, statistics and handover."}</p></div>
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
        {view === "overview" ? <TeamOverview access={selected} userId={userId} /> : null}
        {view === "people" ? <TeamPeoplePanel access={selected} userId={userId} /> : null}
        {view === "activity" ? <TeamActivityPanel teamId={selected.teamId} userId={userId} /> : null}
        {view === "board" && (selected.unitKind === "TEAM" || !selected.unitKind) ? <TeamBoardPage access={selected} /> : null}
        {view === "calendar" ? <CalendarPage access={selected} /> : null}
        {view === "planning" && capabilities.planning && (selected.unitKind === "TEAM" || !selected.unitKind) ? <TeamPlanningPage access={selected} /> : null}
        {view === "queue" ? <RoutingQueuePanel role={session!.user.role} userId={userId} /> : null}
        {view === "handover" ? <WorkspaceCollaborationPanel access={selected} userId={userId} /> : null}
        {view === "statistics" ? <WorkspaceStatistics access={selected} userId={userId} /> : null}
      </Suspense>
    </main>
  );
}

function TeamOverview({ access, userId }: { access: import("../../lib/api/teamTypes").TeamWorkspaceAccess; userId: string }) {
  const teamId = access.teamId;
  const query = useQuery({ queryKey: protectedQueryKeys.teamWorkspace(userId, teamId), queryFn: () => api.teamWorkspace(teamId) });
  if (query.isPending) return <PageState kind="loading" title="Loading team overview" />;
  if (query.isError) return <Retry onRetry={() => void query.refetch()} />;
  const data = query.data;
  return (
    <>
      <section aria-label="Team overview measures" className="team-metrics">
        <Measure label="Managers" value={data.managerCount} />
        <Measure label={access.unitKind === "TEAM" || !access.unitKind ? "Analysts" : "Members"} value={access.unitKind === "TEAM" || !access.unitKind ? data.analystCount : data.memberCount ?? 0} />
        <Measure label="Active work" value={data.activeWorkCount} />
        <Measure label="Due in 7 days" value={data.dueSoonCount} />
        <Measure label="Overdue" value={data.overdueCount} attention={data.overdueCount > 0} />
      </section>
      <TeamStatisticsStrip teamId={teamId} userId={userId} />
      <nav aria-label="Workspace overview destinations" className="team-overview-links">
        {(access.unitKind === "TEAM" || !access.unitKind ? deliveryViews : routingViews).slice(1, 6).map(([key, label]) => <Link key={key} to={`/teams/${teamId}/${key}`}>{label}</Link>)}
        <Link to="/my-work">My work</Link>
      </nav>
      <section className="team-overview-note"><span>Workspace authority</span><h2>One team, one operational picture</h2><p>Requests remain controlled by the human-led Camunda workflow. Membership, calendar, package and capacity records provide the surrounding delivery context without replacing workflow authority.</p></section>
    </>
  );
}

function WorkspaceStatistics({ access, userId }: { access: import("../../lib/api/teamTypes").TeamWorkspaceAccess; userId: string }) {
  return <section className="workspace-statistics"><header><span>Authorised unit and descendants</span><h2>Operational statistics</h2><p>Measures follow the organisation hierarchy. Sibling and parent branches remain outside this workspace.</p></header><TeamStatisticsStrip teamId={access.teamId} userId={userId} /></section>;
}

function TeamStatisticsStrip({ teamId, userId }: { teamId: string; userId: string }) {
  const scopes = useQuery({ queryKey: protectedQueryKeys.statisticsScopes(userId), queryFn: api.statisticsScopes });
  const scope = scopes.data?.items.find((item) => item.unitId === teamId);
  const statistics = useQuery({
    queryKey: protectedQueryKeys.statistics(userId, scope?.id ?? "", teamId, overviewFrom, overviewTo, "Europe/London"),
    queryFn: () => api.statistics({ scopeId: scope!.id, unitId: teamId, from: overviewFrom, to: overviewTo, timeZone: "Europe/London" }),
    enabled: Boolean(scope),
  });
  if (!scope || !statistics.data) return null;
  const metrics = new Map(statistics.data.summary.map((metric) => [metric.key, metric.value]));
  return <section aria-label="Team service measures" className="team-service-strip"><div><span>Received in 30 days</span><strong>{metrics.get("received") ?? 0}</strong></div><div><span>Completed</span><strong>{metrics.get("completed") ?? 0}</strong></div><div><span>Products released</span><strong>{metrics.get("released") ?? 0}</strong></div><Link to={`/statistics?scopeId=${encodeURIComponent(scope.id)}&unitId=${encodeURIComponent(teamId)}`}>Full statistics</Link></section>;
}

function Measure({ label, value, attention = false }: { label: string; value: number; attention?: boolean }) {
  return <div className={attention ? "team-metric team-metric--attention" : "team-metric"}><span>{label}</span><strong>{value}</strong></div>;
}

function Retry({ onRetry }: { onRetry: () => void }) {
  return <PageState action={<button className="button" onClick={onRetry}>Try again</button>} kind="error" title="Team workspace could not be loaded">Check your connection and current team access.</PageState>;
}
