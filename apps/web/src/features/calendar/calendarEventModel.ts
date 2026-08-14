import type {
  CalendarCategory,
  CalendarEventInput,
  CalendarVisibility,
  RecurrenceFrequency,
} from "../../lib/api/calendarTypes";
import type { TeamMember } from "../../lib/api/teamTypes";
import { localInput } from "./calendarDates";

export type CalendarEventMode = "personal" | "team" | "commitment";

export type CalendarEventDraft = {
  allDay: boolean;
  category: CalendarCategory;
  endsAt: string;
  interval: number;
  mode: CalendarEventMode;
  notes: string;
  recurrence: RecurrenceFrequency;
  requestId: string;
  startsAt: string;
  subjectId: string;
  timeZone: string;
  title: string;
  until: string;
  visibility: CalendarVisibility;
};

export function initialCalendarEventDraft(now = new Date()): CalendarEventDraft {
  const startsAt = new Date(now.getTime() + 86_400_000);
  return {
    allDay: false,
    category: "OTHER",
    endsAt: localInput(new Date(startsAt.getTime() + 3_600_000)),
    interval: 1,
    mode: "personal",
    notes: "",
    recurrence: "NONE",
    requestId: "",
    startsAt: localInput(startsAt),
    subjectId: "",
    timeZone: "Europe/London",
    title: "",
    until: "",
    visibility: "TEAM_DETAIL",
  };
}

export function calendarEventInput(draft: CalendarEventDraft): CalendarEventInput {
  return {
    allDay: draft.allDay,
    category: draft.category,
    endsAt: new Date(draft.endsAt).toISOString(),
    notes: draft.notes,
    recurrence: draft.recurrence,
    recurrenceInterval: draft.interval,
    recurrenceUntil: draft.recurrence === "NONE" ? null : new Date(draft.until).toISOString(),
    startsAt: new Date(draft.startsAt).toISOString(),
    timeZone: draft.timeZone,
    title: draft.title,
    visibility: draft.visibility,
  };
}

export function currentAnalysts(members: TeamMember[] = []) {
  return members.filter(
    (member) => member.state === "CURRENT" && member.role === "DELIVERY_SPECIALIST",
  );
}

export function draftForDate(draft: CalendarEventDraft, initialDate: Date): CalendarEventDraft {
  const startsAt = new Date(initialDate);
  startsAt.setHours(9, 0, 0, 0);
  return {
    ...draft,
    endsAt: localInput(new Date(startsAt.getTime() + 3_600_000)),
    startsAt: localInput(startsAt),
  };
}

export function clearedCalendarEventDraft(draft: CalendarEventDraft): CalendarEventDraft {
  return { ...draft, notes: "", requestId: "", subjectId: "", title: "" };
}
