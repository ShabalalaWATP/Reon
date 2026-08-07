import type { CalendarOccurrence } from "../../lib/api/calendarTypes";
import { addDays, calendarRange, sameDay, type CalendarView } from "./calendarDates";

export function CalendarViews({
  anchor,
  items,
  onSelect,
  view,
}: {
  anchor: Date;
  items: CalendarOccurrence[];
  onSelect: (item: CalendarOccurrence) => void;
  view: CalendarView;
}) {
  if (view === "agenda") return <Agenda items={items} onSelect={onSelect} />;
  const { start } = calendarRange(anchor, view);
  const count = view === "month" ? 42 : 7;
  const days = Array.from({ length: count }, (_, index) => addDays(start, index));
  return (
    <section aria-label={`${view} calendar`} className={`calendar-grid calendar-grid--${view}`}>
      {days.map((day) => (
        <Day
          anchor={anchor}
          day={day}
          items={items.filter((item) => sameDay(new Date(item.startsAt), day))}
          key={day.toISOString()}
          onSelect={onSelect}
          view={view}
        />
      ))}
    </section>
  );
}

function Day({
  anchor,
  day,
  items,
  onSelect,
  view,
}: {
  anchor: Date;
  day: Date;
  items: CalendarOccurrence[];
  onSelect: (item: CalendarOccurrence) => void;
  view: CalendarView;
}) {
  const outside = view === "month" && day.getMonth() !== anchor.getMonth();
  const today = sameDay(day, new Date());
  return (
    <article className={`calendar-day${outside ? " calendar-day--outside" : ""}${today ? " calendar-day--today" : ""}`}>
      <header><span>{new Intl.DateTimeFormat("en-GB", { weekday: "short" }).format(day)}</span><strong>{day.getDate()}</strong></header>
      {items.length === 0 ? <span className="calendar-day__empty">Available</span> : (
        <ol>{items.map((item) => <li key={`${item.eventId}-${item.occurrenceStart}`}><OccurrenceButton item={item} onSelect={onSelect} /></li>)}</ol>
      )}
    </article>
  );
}

function Agenda({ items, onSelect }: { items: CalendarOccurrence[]; onSelect: (item: CalendarOccurrence) => void }) {
  const days = groupByDay(items);
  if (days.length === 0) return <section className="calendar-empty"><h2>No calendar activity</h2><p>This range has no recorded events or commitments.</p></section>;
  return (
    <section aria-label="Agenda" className="calendar-agenda">
      {days.map(([day, occurrences]) => (
        <article key={day}>
          <header><span>{new Intl.DateTimeFormat("en-GB", { weekday: "long" }).format(new Date(day))}</span><h2>{new Intl.DateTimeFormat("en-GB", { dateStyle: "long" }).format(new Date(day))}</h2></header>
          <ol>{occurrences.map((item) => <li key={`${item.eventId}-${item.occurrenceStart}`}><OccurrenceButton item={item} onSelect={onSelect} /></li>)}</ol>
        </article>
      ))}
    </section>
  );
}

function OccurrenceButton({ item, onSelect }: { item: CalendarOccurrence; onSelect: (item: CalendarOccurrence) => void }) {
  const time = item.allDay ? "All day" : new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit" }).format(new Date(item.startsAt));
  return (
    <button className={`calendar-event calendar-event--${item.category.toLowerCase()}`} onClick={() => onSelect(item)} type="button">
      <span>{time}</span><strong>{item.title}</strong><small>{item.subjectDisplayName}</small>
    </button>
  );
}

function groupByDay(items: CalendarOccurrence[]): Array<[string, CalendarOccurrence[]]> {
  const grouped = new Map<string, CalendarOccurrence[]>();
  items.forEach((item) => {
    const date = new Date(item.startsAt);
    const key = new Date(date.getFullYear(), date.getMonth(), date.getDate()).toISOString();
    grouped.set(key, [...(grouped.get(key) ?? []), item]);
  });
  return [...grouped.entries()].sort(([left], [right]) => left.localeCompare(right));
}
