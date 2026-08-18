import { Link } from "react-router";

import type { CalendarOccurrence } from "../../lib/api/calendarTypes";
import { boardLabel } from "../board/boardPresentation";

type UpcomingTeamCalendarProps = {
  error: boolean;
  heading: string;
  items: CalendarOccurrence[];
  pending: boolean;
  teamId: string;
};

export function UpcomingTeamCalendar({
  error,
  heading,
  items,
  pending,
  teamId,
}: UpcomingTeamCalendarProps) {
  return (
    <section className="team-home__list">
      <header>
        <h2>{heading}</h2>
        <Link to={`/teams/${teamId}/calendar`}>Open Calendar</Link>
      </header>
      <ol>
        {items.map((item) => (
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
        {!pending && items.length === 0 ? (
          <li className="inline-empty">No events in the next 14 days.</li>
        ) : null}
        {error ? (
          <li>
            <span className="inline-unavailable">Calendar unavailable</span>
          </li>
        ) : null}
      </ol>
    </section>
  );
}
