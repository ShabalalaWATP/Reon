import type { CalendarOccurrence } from "../../lib/api/calendarTypes";
import { addDays, calendarRange, sameDay, type CalendarView } from "./calendarDates";

const shortWeekday = new Intl.DateTimeFormat("en-GB", { weekday: "short" });
const longWeekday = new Intl.DateTimeFormat("en-GB", { weekday: "long" });
const longDate = new Intl.DateTimeFormat("en-GB", { dateStyle: "long" });
const clockTime = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit" });

export function CalendarViews({
  anchor,
  items,
  onCreate,
  onSelect,
  view,
}: {
  anchor: Date;
  items: CalendarOccurrence[];
  onCreate?: (day: Date) => void;
  onSelect: (item: CalendarOccurrence) => void;
  view: CalendarView;
}) {
  if (view === "agenda") return <Agenda items={items} onSelect={onSelect} />;
  const { start } = calendarRange(anchor, view);
  const count = view === "month" ? 42 : 7;
  const days = Array.from({ length: count }, (_, index) => addDays(start, index));
  const itemsByDay = groupItemsByLocalDay(items);
  return (
    <section aria-label={`${view} calendar`} className={`calendar-grid calendar-grid--${view}`}>
      {days.map((day) => (
        <Day
          anchor={anchor}
          day={day}
          items={itemsByDay.get(localDayKey(day)) ?? []}
          key={day.toISOString()}
          onSelect={onSelect}
          onCreate={onCreate}
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
  onCreate,
  view,
}: {
  anchor: Date;
  day: Date;
  items: CalendarOccurrence[];
  onSelect: (item: CalendarOccurrence) => void;
  onCreate?: (day: Date) => void;
  view: CalendarView;
}) {
  const outside = view === "month" && day.getMonth() !== anchor.getMonth();
  const today = sameDay(day, new Date());
  return (
    <article className={`calendar-day${outside ? " calendar-day--outside" : ""}${today ? " calendar-day--today" : ""}`}>
      <header><span>{shortWeekday.format(day)}</span><strong>{day.getDate()}</strong></header>
      {items.length === 0 ? <button aria-label={`Add event on ${longDate.format(day)}`} className="calendar-day__empty" onClick={() => onCreate?.(day)} type="button">Add event</button> : (
        <ol>{items.map((item) => <li key={`${item.eventId}-${item.occurrenceStart}`}><OccurrenceButton item={item} onSelect={onSelect} /></li>)}</ol>
      )}
      {items.length > 0 && onCreate ? <button aria-label={`Add event on ${longDate.format(day)}`} className="calendar-day__add" onClick={() => onCreate(day)} type="button">+</button> : null}
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
          <header><span>{longWeekday.format(new Date(day))}</span><h2>{longDate.format(new Date(day))}</h2></header>
          <ol>{occurrences.map((item) => <li key={`${item.eventId}-${item.occurrenceStart}`}><OccurrenceButton item={item} onSelect={onSelect} /></li>)}</ol>
        </article>
      ))}
    </section>
  );
}

function OccurrenceButton({ item, onSelect }: { item: CalendarOccurrence; onSelect: (item: CalendarOccurrence) => void }) {
  const time = item.allDay ? "All day" : clockTime.format(new Date(item.startsAt));
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

function groupItemsByLocalDay(items: CalendarOccurrence[]) {
  const grouped = new Map<string, CalendarOccurrence[]>();
  for (const item of items) {
    const key = localDayKey(new Date(item.startsAt));
    grouped.set(key, [...(grouped.get(key) ?? []), item]);
  }
  return grouped;
}

function localDayKey(value: Date) {
  return `${value.getFullYear()}-${value.getMonth()}-${value.getDate()}`;
}
