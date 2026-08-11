import { useQuery } from "@tanstack/react-query";
import { type ReactNode, useMemo } from "react";
import { Link } from "react-router";

import { boardApi } from "../../lib/api/boardClient";
import type { BoardFilters } from "../../lib/api/boardTypes";
import { api } from "../../lib/api/client";
import { planningEvolutionApi } from "../../lib/api/planningEvolutionClient";
import type { PlanningCockpit } from "../../lib/api/planningEvolutionTypes";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type {
  TeamWorkspaceAccess,
  TeamWorkspaceOverview,
} from "../../lib/api/teamTypes";
import { addLocalDays } from "../../lib/dateInputs";
import { boardLabel } from "../board/boardPresentation";

const requestBoardFilters: Partial<BoardFilters> = { itemTypes: ["SERVICE_REQUEST"] };

export function DeliveryTeamHome({ access, overview, userId }: { access: TeamWorkspaceAccess; overview: TeamWorkspaceOverview; userId: string }) {
  const [calendarFrom, calendarTo] = useMemo(() => {
    const now = new Date();
    return [now.toISOString(), addLocalDays(now, 14).toISOString()];
  }, []);
  const board = useQuery({
    queryKey: protectedQueryKeys.teamBoard(userId, access.teamId, "home-requests"),
    queryFn: () => boardApi.board(access.teamId, requestBoardFilters, { limit: 8 }),
  });
  const planning = useQuery({
    queryKey: protectedQueryKeys.teamPlanningCockpit(userId, access.teamId),
    queryFn: () => planningEvolutionApi.cockpit(access.teamId),
    enabled: Boolean(access.views?.includes("PLANNING")),
  });
  const people = useQuery({ queryKey: protectedQueryKeys.teamPeople(userId, access.teamId), queryFn: () => api.teamPeople(access.teamId) });
  const calendar = useQuery({ queryKey: protectedQueryKeys.teamCalendar(userId, access.teamId, calendarFrom, calendarTo), queryFn: () => api.teamCalendar(access.teamId, calendarFrom, calendarTo) });
  const records = useQuery({ queryKey: protectedQueryKeys.workspaceRecords(userId, access.teamId), queryFn: () => api.workspaceRecords(access.teamId) });
  const activity = useQuery({ queryKey: protectedQueryKeys.teamActivity(userId, access.teamId), queryFn: () => api.teamActivity(access.teamId) });
  const counts = board.data?.columnCounts;
  const openRecords = records.data?.items.filter((item) => item.status === "OPEN") ?? [];
  const upcoming = calendar.data?.items.slice(0, 5) ?? [];
  const currentPeople = people.data?.items.filter((item) => item.state === "CURRENT") ?? [];
  return (
    <div className="team-home">
      <section aria-labelledby="team-attention-title" className="team-home__attention">
        <header><span>Current decisions</span><h2 id="team-attention-title">Team attention</h2><p>Open the exact work behind each signal.</p></header>
        <div className="team-attention-list">
          <AttentionLink attention={overview.overdueCount > 0} count={overview.overdueCount} label="Overdue" note="Past the customer-required date" to={`/teams/${access.teamId}/board?preset=overdue`} />
          <AttentionLink count={counts?.AWAITING_ASSIGNMENT ?? 0} label="Needs assignment" note="Awaiting a Lead Analyst" to={`/teams/${access.teamId}/board?preset=needs-assignment`} />
          <AttentionLink attention={Boolean(counts?.BLOCKED)} count={counts?.BLOCKED ?? 0} label="Waiting for customer" note="An Analyst requested clarification" to={`/teams/${access.teamId}/board?preset=blocked`} />
          <AttentionLink attention={Boolean(counts?.MANAGER_REVIEW)} count={counts?.MANAGER_REVIEW ?? 0} label="Manager review" note="Completed work awaiting checks" to={`/teams/${access.teamId}/board?preset=manager-review`} />
          <AttentionLink count={overview.dueSoonCount} label="Due in seven days" note="Upcoming delivery commitments" to={`/teams/${access.teamId}/board?preset=due-week`} />
        </div>
        {board.isError ? <InlineUnavailable label="Board attention" /> : null}
      </section>

      <section className="team-home__planning">
        <header><span>Capacity and flow</span><h2>Delivery outlook</h2><Link to={`/teams/${access.teamId}/planning`}>Open Planning</Link></header>
        {planning.data ? <div className="team-home__measures">
          <HomeMeasure label="Backlog" value={planning.data.summary.backlogCount} />
          <HomeMeasure attention={planning.data.summary.blockedCount > 0} label="Blocked" value={planning.data.summary.blockedCount} />
          <HomeMeasure attention={planning.data.summary.dueRiskCount > 0} label="Due risk" value={planning.data.summary.dueRiskCount} />
          <HomeMeasure label="Available" value={formatMinutes(planning.data.summary.availableMinutes)} />
          <HomeMeasure label="Reserved" value={formatMinutes(planning.data.summary.reservedMinutes)} />
        </div> : <InlineUnavailable label={planning.isPending ? "Loading delivery outlook" : "Delivery outlook"} />}
        {planning.data?.iteration ? <p className="team-home__iteration"><strong>{planning.data.iteration.name}</strong><span>{planning.data.iteration.completedPoints} of {planning.data.iteration.committedPoints} points complete</span></p> : null}
        {planning.data ? <PlanningAlerts planning={planning.data} /> : null}
      </section>

      <div className="team-home__columns">
        <HomeList heading="Upcoming team calendar" link={`/teams/${access.teamId}/calendar`} linkLabel="Open Calendar">
          {upcoming.map((item) => <li key={`${item.eventId}-${item.occurrenceStart}`}><time>{new Date(item.startsAt).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}</time><strong>{item.title}</strong><small>{item.subjectDisplayName} · {boardLabel(item.category)}</small></li>)}
          {!calendar.isPending && upcoming.length === 0 ? <li className="inline-empty">No events in the next 14 days.</li> : null}
          {calendar.isError ? <li><InlineUnavailable label="Calendar" /></li> : null}
        </HomeList>
        <HomeList heading="People and current load" link={`/teams/${access.teamId}/people`} linkLabel="Open People">
          {currentPeople.slice(0, 7).map((item) => <li key={item.membershipId}><strong>{item.displayName}</strong><small>{item.workspacePosition?.toLowerCase() ?? "member"} · {item.activeWorkCount} active work item{item.activeWorkCount === 1 ? "" : "s"}{item.skills.length ? ` · ${item.skills.slice(0, 3).join(", ")}` : ""}</small></li>)}
          {people.isError ? <li><InlineUnavailable label="People" /></li> : null}
        </HomeList>
      </div>

      <div className="team-home__columns">
        <HomeList heading="Open handover and risks" link={`/teams/${access.teamId}/handover`} linkLabel="Open Handover">
          {openRecords.slice(0, 5).map((item) => <li key={item.id}><span className="team-home__kind">{boardLabel(item.kind)}</span><strong>{item.title}</strong><small>Updated {new Date(item.updatedAt).toLocaleDateString("en-GB")}</small></li>)}
          {!records.isPending && openRecords.length === 0 ? <li className="inline-empty">No open handover records or risks.</li> : null}
          {records.isError ? <li><InlineUnavailable label="Handover" /></li> : null}
        </HomeList>
        <HomeList heading="Recent team activity" link={`/teams/${access.teamId}/activity`} linkLabel="Open Activity">
          {activity.data?.items.slice(0, 5).map((item) => <li key={item.id}><time>{new Date(item.createdAt).toLocaleDateString("en-GB")}</time><strong>{item.summary}</strong><small>{item.actorDisplayName ?? "System"}</small></li>)}
          {!activity.isPending && activity.data?.items.length === 0 ? <li className="inline-empty">No recent team activity.</li> : null}
          {activity.isError ? <li><InlineUnavailable label="Activity" /></li> : null}
        </HomeList>
      </div>
    </div>
  );
}

function AttentionLink({ attention = false, count, label, note, to }: { attention?: boolean; count: number; label: string; note: string; to: string }) {
  return <Link className={attention ? "team-attention team-attention--urgent" : "team-attention"} to={to}><strong>{count}</strong><span>{label}<small>{note}</small></span><em>Open</em></Link>;
}

function HomeMeasure({ attention = false, label, value }: { attention?: boolean; label: string; value: number | string }) {
  return <div className={attention ? "team-home__measure team-home__measure--attention" : "team-home__measure"}><span>{label}</span><strong>{value}</strong></div>;
}

function HomeList({ children, heading, link, linkLabel }: { children: ReactNode; heading: string; link: string; linkLabel: string }) {
  return <section className="team-home__list"><header><h2>{heading}</h2><Link to={link}>{linkLabel}</Link></header><ol>{children}</ol></section>;
}

function PlanningAlerts({ planning }: { planning: PlanningCockpit }) {
  const warnings = [
    ...planning.blockers.map((item) => ({ key: `blocker-${item.packageId}`, label: `${item.reference} blocked for ${item.ageDays} day${item.ageDays === 1 ? "" : "s"}`, detail: item.reason })),
    ...planning.dependencies.filter((item) => item.status !== "CLEAR").map((item) => ({ key: `dependency-${item.packageId}-${item.dependencyReference}`, label: `${item.reference} depends on ${item.dependencyReference}`, detail: item.warning })),
  ].slice(0, 4);
  return <div className="team-home__planning-alerts"><p><strong>Advisory planning signals</strong><span>{planning.freshness.label} · generated {new Date(planning.generatedAt).toLocaleString("en-GB")}</span></p>{warnings.length ? <ul>{warnings.map((item) => <li key={item.key}><strong>{item.label}</strong><span>{item.detail}</span></li>)}</ul> : <small>No blocker-age or dependency warnings.</small>}</div>;
}

function InlineUnavailable({ label }: { label: string }) { return <span className="inline-unavailable">{label} unavailable</span>; }
function formatMinutes(value: number) { return `${Math.floor(value / 60)}h ${value % 60}m`; }
