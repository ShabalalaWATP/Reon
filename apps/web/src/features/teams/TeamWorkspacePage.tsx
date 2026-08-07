import { useQuery } from "@tanstack/react-query";
import { NavLink, Navigate, useNavigate, useParams } from "react-router";

import { PageState } from "../../components/PageState";
import { CalendarPage } from "../calendar/CalendarPage";
import { TeamBoardPage } from "../board/TeamBoardPage";
import { TeamPlanningPage } from "../board/TeamPlanningPage";
import { api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import { useAuth } from "../../lib/auth/AuthProvider";
import { useCapabilities } from "../../lib/capabilities/useCapabilities";
import { TeamActivityPanel } from "./TeamActivityPanel";
import { TeamPeoplePanel } from "./TeamPeoplePanel";

const views = [
  ["overview", "Overview"],
  ["board", "Board"],
  ["calendar", "Calendar"],
  ["people", "People"],
  ["planning", "Planning"],
  ["activity", "Activity"],
] as const;

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
  const availableViews = capabilities.planning ? views : views.filter(([key]) => key !== "planning");
  if (!availableViews.some(([key]) => key === view)) {
    return <Navigate replace to={`/teams/${selected.teamId}/overview`} />;
  }
  return (
    <main className="page-stack team-workspace">
      <header className="team-heading">
        <div><span>{selected.teamCode}</span><h1>{selected.teamName}</h1><p>Shared delivery workspace for staffing, service work and team planning.</p></div>
        {workspaces.data.items.length > 1 ? (
          <label className="form-field">Team
            <select onChange={(event) => { void navigate(`/teams/${event.target.value}/overview`); }} value={selected.teamId}>
              {workspaces.data.items.map((team) => <option key={team.teamId} value={team.teamId}>{team.teamName}</option>)}
            </select>
          </label>
        ) : null}
      </header>
      <nav aria-label="Team workspace views" className="team-tabs">
        {availableViews.map(([key, label]) => <NavLink className={({ isActive }) => isActive ? "team-tab team-tab--active" : "team-tab"} key={key} to={`/teams/${selected.teamId}/${key}`}>{label}</NavLink>)}
      </nav>
      {view === "overview" ? <TeamOverview teamId={selected.teamId} userId={userId} /> : null}
      {view === "people" ? <TeamPeoplePanel access={selected} userId={userId} /> : null}
      {view === "activity" ? <TeamActivityPanel teamId={selected.teamId} userId={userId} /> : null}
      {view === "board" ? <TeamBoardPage access={selected} /> : null}
      {view === "calendar" ? <CalendarPage access={selected} /> : null}
      {view === "planning" && capabilities.planning ? <TeamPlanningPage access={selected} /> : null}
    </main>
  );
}

function TeamOverview({ teamId, userId }: { teamId: string; userId: string }) {
  const query = useQuery({ queryKey: protectedQueryKeys.teamWorkspace(userId, teamId), queryFn: () => api.teamWorkspace(teamId) });
  if (query.isPending) return <PageState kind="loading" title="Loading team overview" />;
  if (query.isError) return <Retry onRetry={() => void query.refetch()} />;
  const data = query.data;
  return (
    <>
      <section aria-label="Team overview measures" className="team-metrics">
        <Measure label="Managers" value={data.managerCount} />
        <Measure label="Analysts" value={data.analystCount} />
        <Measure label="Active work" value={data.activeWorkCount} />
        <Measure label="Due in 7 days" value={data.dueSoonCount} />
        <Measure label="Overdue" value={data.overdueCount} attention={data.overdueCount > 0} />
      </section>
      <section className="team-overview-note"><span>Workspace authority</span><h2>One team, one operational picture</h2><p>Requests remain controlled by the human-led Camunda workflow. Membership, calendar, package and capacity records provide the surrounding delivery context without replacing workflow authority.</p></section>
    </>
  );
}

function Measure({ label, value, attention = false }: { label: string; value: number; attention?: boolean }) {
  return <div className={attention ? "team-metric team-metric--attention" : "team-metric"}><span>{label}</span><strong>{value}</strong></div>;
}

function Retry({ onRetry }: { onRetry: () => void }) {
  return <PageState action={<button className="button" onClick={onRetry}>Try again</button>} kind="error" title="Team workspace could not be loaded">Check your connection and current team access.</PageState>;
}
