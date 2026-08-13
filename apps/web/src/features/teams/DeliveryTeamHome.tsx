import { useQuery } from "@tanstack/react-query";
import { type ReactNode, useMemo } from "react";
import { Link } from "react-router";

import { boardApi } from "../../lib/api/boardClient";
import type { BoardFilters } from "../../lib/api/boardTypes";
import { api } from "../../lib/api/client";
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
  const people = useQuery({ queryKey: protectedQueryKeys.teamPeople(userId, access.teamId), queryFn: () => api.teamPeople(access.teamId) });
  const calendar = useQuery({ queryKey: protectedQueryKeys.teamCalendar(userId, access.teamId, calendarFrom, calendarTo), queryFn: () => api.teamCalendar(access.teamId, calendarFrom, calendarTo) });
  const activity = useQuery({ queryKey: protectedQueryKeys.teamActivity(userId, access.teamId), queryFn: () => api.teamActivity(access.teamId) });
  const counts = board.data?.columnCounts;
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

      <div className="team-home__columns">
        <HomeList heading="Upcoming team calendar" link={`/teams/${access.teamId}/calendar`} linkLabel="Open Calendar">
          {upcoming.map((item) => <li key={`${item.eventId}-${item.occurrenceStart}`}><time>{new Date(item.startsAt).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}</time><strong>{item.title}</strong><small>{item.subjectDisplayName} · {boardLabel(item.category)}</small></li>)}
          {!calendar.isPending && upcoming.length === 0 ? <li className="inline-empty">No events in the next 14 days.</li> : null}
          {calendar.isError ? <li><InlineUnavailable label="Calendar" /></li> : null}
        </HomeList>
        <HomeList heading="People and current load" link={`/teams/${access.teamId}/people`} linkLabel="Open People">
          {currentPeople.slice(0, 7).map((item) => <li key={item.membershipId}><strong>{item.displayName}</strong><small>{item.workspacePosition?.toLowerCase() ?? "member"} · {item.activeWorkCount} active work item{item.activeWorkCount === 1 ? "" : "s"}{item.skills?.length ? ` · ${item.skills.slice(0, 3).join(", ")}` : ""}</small></li>)}
          {people.isError ? <li><InlineUnavailable label="People" /></li> : null}
        </HomeList>
      </div>

      <div className="team-home__columns team-home__columns--single">
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

function HomeList({ children, heading, link, linkLabel }: { children: ReactNode; heading: string; link: string; linkLabel: string }) {
  return <section className="team-home__list"><header><h2>{heading}</h2><Link to={link}>{linkLabel}</Link></header><ol>{children}</ol></section>;
}

function InlineUnavailable({ label }: { label: string }) { return <span className="inline-unavailable">{label} unavailable</span>; }
