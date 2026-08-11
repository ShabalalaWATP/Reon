import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { Link } from "react-router";

import { api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { TeamWorkspaceAccess, TeamWorkspaceOverview } from "../../lib/api/teamTypes";
import type { WorkItem } from "../../lib/api/types";
import { addLocalDays } from "../../lib/dateInputs";
import { elapsedTime } from "../../lib/serviceTiming";
import { statusLabels } from "../../lib/status";
import { boardLabel } from "../board/boardPresentation";

export function RoutingTeamHome({ access, overview, userId }: { access: TeamWorkspaceAccess; overview: TeamWorkspaceOverview; userId: string }) {
  const [from, to] = useMemo(() => {
    const now = new Date();
    return [now.toISOString(), addLocalDays(now, 14).toISOString()];
  }, []);
  const queue = useQuery({ queryKey: protectedQueryKeys.workItems(userId, access.teamId), queryFn: () => api.workItems(undefined, access.teamId) });
  const calendar = useQuery({ queryKey: protectedQueryKeys.teamCalendar(userId, access.teamId, from, to), queryFn: () => api.teamCalendar(access.teamId, from, to) });
  const activity = useQuery({ queryKey: protectedQueryKeys.teamActivity(userId, access.teamId), queryFn: () => api.teamActivity(access.teamId) });
  const items = queue.data?.items ?? [];
  const available = items.filter((item) => !item.assigneeId);
  const mine = items.filter((item) => item.assigneeId === userId);
  const information = items.filter((item) => item.stage.includes("INFORMATION"));
  const oldest = [...items].sort((left, right) => left.createdAt.localeCompare(right.createdAt))[0];
  const stages = stageCounts(items);
  return (
    <div className="team-home routing-home">
      <section className="routing-home__decision" aria-labelledby="routing-decision-title">
        <header><span>Human-led routing</span><h2 id="routing-decision-title">Routing decisions</h2><p>Claim and complete your own decision. Manager position does not add an approval stage.</p></header>
        <div className="team-home__measures">
          <HomeMeasure attention={available.length > 0} label="Available to claim" value={available.length} />
          <HomeMeasure label="Claimed by you" value={mine.length} />
          <HomeMeasure attention={information.length > 0} label="Information required" value={information.length} />
          <HomeMeasure label="Oldest wait" value={oldest ? elapsedTime(oldest.createdAt) : "None"} />
          <HomeMeasure label="Active branch work" value={overview.activeWorkCount} />
        </div>
        <div className="routing-home__actions"><Link className="button button--primary" to={`/teams/${access.teamId}/queue`}>Open work queue</Link></div>
        {queue.isError ? <p className="inline-unavailable">Routing queue unavailable</p> : null}
      </section>

      <div className="team-home__columns">
        <section className="team-home__list"><header><h2>Current stages</h2><Link to={`/teams/${access.teamId}/queue`}>Open Queue</Link></header>{stages.length ? <ol>{stages.map(([stage, count]) => <li key={stage}><strong>{statusLabels[stage as WorkItem["stage"]] ?? boardLabel(stage)}</strong><small>{count} visible decision{count === 1 ? "" : "s"}</small></li>)}</ol> : <p className="inline-empty">No routing decisions are currently visible.</p>}</section>
        <section className="team-home__list"><header><h2>Upcoming unit calendar</h2><Link to={`/teams/${access.teamId}/calendar`}>Open Calendar</Link></header><ol>{calendar.data?.items.slice(0, 5).map((item) => <li key={`${item.eventId}-${item.occurrenceStart}`}><time>{new Date(item.startsAt).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}</time><strong>{item.title}</strong><small>{item.subjectDisplayName} · {boardLabel(item.category)}</small></li>)}{!calendar.isPending && calendar.data?.items.length === 0 ? <li className="inline-empty">No events in the next 14 days.</li> : null}{calendar.isError ? <li className="inline-unavailable">Calendar unavailable</li> : null}</ol></section>
      </div>

      <div className="team-home__columns team-home__columns--single">
        <section className="team-home__list"><header><h2>Recent unit activity</h2><Link to={`/teams/${access.teamId}/activity`}>Open Activity</Link></header><ol>{activity.data?.items.slice(0, 5).map((item) => <li key={item.id}><time>{new Date(item.createdAt).toLocaleDateString("en-GB")}</time><strong>{item.summary}</strong><small>{item.actorDisplayName ?? "System"}</small></li>)}{!activity.isPending && activity.data?.items.length === 0 ? <li className="inline-empty">No recent unit activity.</li> : null}{activity.isError ? <li className="inline-unavailable">Activity unavailable</li> : null}</ol></section>
      </div>
    </div>
  );
}

function HomeMeasure({ attention = false, label, value }: { attention?: boolean; label: string; value: number | string }) {
  return <div className={attention ? "team-home__measure team-home__measure--attention" : "team-home__measure"}><span>{label}</span><strong>{value}</strong></div>;
}

function stageCounts(items: WorkItem[]) {
  const counts = new Map<string, number>();
  items.forEach((item) => counts.set(item.stage, (counts.get(item.stage) ?? 0) + 1));
  return [...counts.entries()].sort((left, right) => right[1] - left[1]);
}
