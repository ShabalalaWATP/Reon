import { Link } from "react-router";

import type { TeamWorkspaceAccess, TeamWorkspaceOverview } from "../../lib/api/teamTypes";
import type { Session, WorkItem } from "../../lib/api/types";
import { elapsedTime } from "../../lib/serviceTiming";
import { statusLabels } from "../../lib/status";
import { boardLabel } from "../board/boardPresentation";
import { hasWorkspaceView, useRoutingTeamHomeData, type RoutingHomeData } from "./useTeamHomeData";

export function RoutingTeamHome({
  access,
  overview,
  session,
}: {
  access: TeamWorkspaceAccess;
  overview: TeamWorkspaceOverview;
  session: Session;
}) {
  const data = useRoutingTeamHomeData(access, session);
  const showActivity = hasWorkspaceView(access, "ACTIVITY");
  const showCalendar = hasWorkspaceView(access, "CALENDAR");
  const showQueue = hasWorkspaceView(access, "QUEUE");
  return (
    <div className="team-home routing-home">
      {showQueue ? <RoutingDecision access={access} data={data} overview={overview} /> : null}
      {showQueue || showCalendar ? (
        <div className="team-home__columns">
          {showQueue ? <CurrentStages data={data} teamId={access.teamId} /> : null}
          {showCalendar ? <UpcomingCalendar data={data} teamId={access.teamId} /> : null}
        </div>
      ) : null}
      {showActivity ? <RecentActivity data={data} teamId={access.teamId} /> : null}
    </div>
  );
}

function RoutingDecision({
  access,
  data,
  overview,
}: {
  access: TeamWorkspaceAccess;
  data: RoutingHomeData;
  overview: TeamWorkspaceOverview;
}) {
  return (
    <section className="routing-home__decision" aria-labelledby="routing-decision-title">
      <header>
        <span>Human-led routing</span>
        <h2 id="routing-decision-title">Routing decisions</h2>
        <p>
          Claim and complete your own decision. Manager position does not add an approval stage.
        </p>
      </header>
      <div className="team-home__measures">
        <HomeMeasure
          attention={data.availableCount > 0}
          label="Available to claim"
          value={data.availableCount}
        />
        <HomeMeasure label="Claimed by you" value={data.mineCount} />
        <HomeMeasure
          attention={data.informationCount > 0}
          label="Information required"
          value={data.informationCount}
        />
        <HomeMeasure
          label="Oldest wait"
          value={data.oldestCreatedAt ? elapsedTime(data.oldestCreatedAt) : "None"}
        />
        {overview.workloadVisible !== false ? (
          <HomeMeasure label="Active branch work" value={overview.activeWorkCount} />
        ) : null}
      </div>
      <div className="routing-home__actions">
        <Link className="button button--primary" to={`/teams/${access.teamId}/queue`}>
          Open work queue
        </Link>
      </div>
      {data.queueError ? <p className="inline-unavailable">Routing queue unavailable</p> : null}
    </section>
  );
}

function CurrentStages({ data, teamId }: { data: RoutingHomeData; teamId: string }) {
  return (
    <section className="team-home__list">
      <header>
        <h2>Current stages</h2>
        <Link to={`/teams/${teamId}/queue`}>Open Queue</Link>
      </header>
      {data.stages.length ? (
        <ol>
          {data.stages.map(([stage, count]) => (
            <li key={stage}>
              <strong>{stageLabel(stage)}</strong>
              <small>
                {count} visible decision{count === 1 ? "" : "s"}
              </small>
            </li>
          ))}
        </ol>
      ) : (
        <p className="inline-empty">No routing decisions are currently visible.</p>
      )}
    </section>
  );
}

function UpcomingCalendar({ data, teamId }: { data: RoutingHomeData; teamId: string }) {
  return (
    <section className="team-home__list">
      <header>
        <h2>Upcoming unit calendar</h2>
        <Link to={`/teams/${teamId}/calendar`}>Open Calendar</Link>
      </header>
      <ol>
        {data.upcoming.map((item) => (
          <li key={`${item.eventId}-${item.occurrenceStart}`}>
            <time>
              {new Date(item.startsAt).toLocaleString("en-GB", {
                dateStyle: "medium",
                timeStyle: "short",
              })}
            </time>
            <strong>{item.title}</strong>
            <small>
              {item.subjectDisplayName} · {boardLabel(item.category)}
            </small>
          </li>
        ))}
        {!data.calendarPending && data.upcoming.length === 0 ? (
          <li className="inline-empty">No events in the next 14 days.</li>
        ) : null}
        {data.calendarError ? <li className="inline-unavailable">Calendar unavailable</li> : null}
      </ol>
    </section>
  );
}

function RecentActivity({ data, teamId }: { data: RoutingHomeData; teamId: string }) {
  return (
    <div className="team-home__columns team-home__columns--single">
      <section className="team-home__list">
        <header>
          <h2>Recent unit activity</h2>
          <Link to={`/teams/${teamId}/activity`}>Open Activity</Link>
        </header>
        <ol>
          {data.activity.map((item) => (
            <li key={item.id}>
              <time>{new Date(item.createdAt).toLocaleDateString("en-GB")}</time>
              <strong>{item.summary}</strong>
              <small>{item.actorDisplayName ?? "System"}</small>
            </li>
          ))}
          {data.activityEmpty ? <li className="inline-empty">No recent unit activity.</li> : null}
          {data.activityError ? <li className="inline-unavailable">Activity unavailable</li> : null}
        </ol>
      </section>
    </div>
  );
}

function HomeMeasure({
  attention = false,
  label,
  value,
}: {
  attention?: boolean;
  label: string;
  value: number | string;
}) {
  return (
    <div
      className={
        attention ? "team-home__measure team-home__measure--attention" : "team-home__measure"
      }
    >
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function stageLabel(stage: string) {
  return statusLabels[stage as WorkItem["stage"]] ?? boardLabel(stage);
}
