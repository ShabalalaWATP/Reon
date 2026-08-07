export type CalendarView = "month" | "week" | "agenda";

export function calendarRange(anchor: Date, view: CalendarView) {
  const start = view === "month" ? monthGridStart(anchor) : startOfWeek(anchor);
  const days = view === "month" ? 42 : view === "week" ? 7 : 30;
  const end = addDays(start, days);
  return { start, end, from: start.toISOString(), to: end.toISOString() };
}

export function moveAnchor(anchor: Date, view: CalendarView, direction: -1 | 1) {
  const result = new Date(anchor);
  if (view === "month") result.setMonth(result.getMonth() + direction);
  else result.setDate(result.getDate() + direction * (view === "week" ? 7 : 30));
  return result;
}

export function startOfWeek(value: Date) {
  const result = startOfDay(value);
  const day = result.getDay() || 7;
  result.setDate(result.getDate() - day + 1);
  return result;
}

export function monthGridStart(value: Date) {
  return startOfWeek(new Date(value.getFullYear(), value.getMonth(), 1));
}

export function addDays(value: Date, count: number) {
  const result = new Date(value);
  result.setDate(result.getDate() + count);
  return result;
}

export function startOfDay(value: Date) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate());
}

export function sameDay(left: Date, right: Date) {
  return left.getFullYear() === right.getFullYear()
    && left.getMonth() === right.getMonth()
    && left.getDate() === right.getDate();
}

export function localInput(value: Date) {
  return new Date(value.getTime() - value.getTimezoneOffset() * 60_000)
    .toISOString().slice(0, 16);
}

export function calendarTitle(anchor: Date, view: CalendarView) {
  if (view === "month") return new Intl.DateTimeFormat("en-GB", { month: "long", year: "numeric" }).format(anchor);
  const range = calendarRange(anchor, view);
  return `${formatShort(range.start)} – ${formatShort(addDays(range.end, -1))}`;
}

function formatShort(value: Date) {
  return new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" }).format(value);
}
