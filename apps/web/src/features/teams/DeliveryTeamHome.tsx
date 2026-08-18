import type { ReactNode } from "react";
import { Link } from "react-router";

import type { Session } from "../../lib/api/types";
import type { TeamWorkspaceAccess, TeamWorkspaceOverview } from "../../lib/api/teamTypes";
import { UpcomingTeamCalendar } from "./UpcomingTeamCalendar";
import {
  hasWorkspaceView,
  useDeliveryTeamHomeData,
  type DeliveryHomeData,
} from "./useTeamHomeData";

export function DeliveryTeamHome({
  access,
  overview,
  session,
}: {
  access: TeamWorkspaceAccess;
  overview: TeamWorkspaceOverview;
  session: Session;
}) {
  const data = useDeliveryTeamHomeData(access, session);
  const showActivity = hasWorkspaceView(access, "ACTIVITY");
  const showBoard = hasWorkspaceView(access, "BOARD");
  const showCalendar = hasWorkspaceView(access, "CALENDAR");
  const showPeople = hasWorkspaceView(access, "PEOPLE");
  return (
    <div className="team-home">
      {showBoard ? <TeamAttention access={access} data={data} overview={overview} /> : null}
      {showCalendar || showPeople ? (
        <div className="team-home__columns">
          {showCalendar ? (
            <UpcomingTeamCalendar
              error={data.calendarError}
              heading="Upcoming team calendar"
              items={data.upcoming}
              pending={data.calendarPending}
              teamId={access.teamId}
            />
          ) : null}
          {showPeople ? <CurrentPeople data={data} teamId={access.teamId} /> : null}
        </div>
      ) : null}
      {showActivity ? <RecentActivity data={data} teamId={access.teamId} /> : null}
    </div>
  );
}

function TeamAttention({
  access,
  data,
  overview,
}: {
  access: TeamWorkspaceAccess;
  data: DeliveryHomeData;
  overview: TeamWorkspaceOverview;
}) {
  const board = `/teams/${access.teamId}/board`;
  return (
    <section aria-labelledby="team-attention-title" className="team-home__attention">
      <header>
        <span>Current decisions</span>
        <h2 id="team-attention-title">Team attention</h2>
        <p>Open the exact work behind each signal.</p>
      </header>
      <div className="team-attention-list">
        <AttentionLink
          attention={overview.overdueCount > 0}
          count={overview.overdueCount}
          label="Overdue"
          note="Past the customer-required date"
          to={`${board}?preset=overdue`}
        />
        <AttentionLink
          count={data.counts?.AWAITING_ASSIGNMENT ?? 0}
          label="Needs assignment"
          note="Awaiting a Lead Analyst"
          to={`${board}?preset=needs-assignment`}
        />
        <AttentionLink
          attention={Boolean(data.counts?.BLOCKED)}
          count={data.counts?.BLOCKED ?? 0}
          label="Waiting for customer"
          note="An Analyst requested clarification"
          to={`${board}?preset=blocked`}
        />
        <AttentionLink
          attention={Boolean(data.counts?.MANAGER_REVIEW)}
          count={data.counts?.MANAGER_REVIEW ?? 0}
          label="Manager review"
          note="Completed work awaiting checks"
          to={`${board}?preset=manager-review`}
        />
        <AttentionLink
          count={overview.dueSoonCount}
          label="Due in seven days"
          note="Upcoming delivery commitments"
          to={`${board}?preset=due-week`}
        />
      </div>
      {data.boardError ? <InlineUnavailable label="Board attention" /> : null}
    </section>
  );
}

function CurrentPeople({ data, teamId }: { data: DeliveryHomeData; teamId: string }) {
  return (
    <HomeList
      heading="People and current load"
      link={`/teams/${teamId}/people`}
      linkLabel="Open People"
    >
      {data.currentPeople.slice(0, 7).map((item) => (
        <li key={item.membershipId}>
          <strong>{item.displayName}</strong>
          <small>
            {item.workspacePosition?.toLowerCase() ?? "member"} · {item.activeWorkCount} active work
            item{item.activeWorkCount === 1 ? "" : "s"}
            {item.skills.length ? ` · ${item.skills.slice(0, 3).join(", ")}` : ""}
          </small>
        </li>
      ))}
      {data.peopleError ? (
        <li>
          <InlineUnavailable label="People" />
        </li>
      ) : null}
    </HomeList>
  );
}

function RecentActivity({ data, teamId }: { data: DeliveryHomeData; teamId: string }) {
  return (
    <div className="team-home__columns team-home__columns--single">
      <HomeList
        heading="Recent team activity"
        link={`/teams/${teamId}/activity`}
        linkLabel="Open Activity"
      >
        {data.activity.map((item) => (
          <li key={item.id}>
            <time>{new Date(item.createdAt).toLocaleDateString("en-GB")}</time>
            <strong>{item.summary}</strong>
            <small>{item.actorDisplayName ?? "System"}</small>
          </li>
        ))}
        {data.activityEmpty ? <li className="inline-empty">No recent team activity.</li> : null}
        {data.activityError ? (
          <li>
            <InlineUnavailable label="Activity" />
          </li>
        ) : null}
      </HomeList>
    </div>
  );
}

function AttentionLink({
  attention = false,
  count,
  label,
  note,
  to,
}: {
  attention?: boolean;
  count: number;
  label: string;
  note: string;
  to: string;
}) {
  return (
    <Link
      className={attention ? "team-attention team-attention--urgent" : "team-attention"}
      to={to}
    >
      <strong>{count}</strong>
      <span>
        {label}
        <small>{note}</small>
      </span>
      <em>Open</em>
    </Link>
  );
}

function HomeList({
  children,
  heading,
  link,
  linkLabel,
}: {
  children: ReactNode;
  heading: string;
  link: string;
  linkLabel: string;
}) {
  return (
    <section className="team-home__list">
      <header>
        <h2>{heading}</h2>
        <Link to={link}>{linkLabel}</Link>
      </header>
      <ol>{children}</ol>
    </section>
  );
}

function InlineUnavailable({ label }: { label: string }) {
  return <span className="inline-unavailable">{label} unavailable</span>;
}
