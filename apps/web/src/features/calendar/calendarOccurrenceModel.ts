import { api } from "../../lib/api/client";
import type { CalendarOccurrence } from "../../lib/api/calendarTypes";
import { localInput } from "./calendarDates";

export type CalendarOccurrenceAction =
  "cancel-occurrence" | "cancel-series" | "edit" | "split" | "dispute" | null;

export type CalendarOccurrenceDraft = {
  action: CalendarOccurrenceAction;
  endsAt: string;
  notes: string;
  reason: string;
  startsAt: string;
  title: string;
  until: string;
};

export type CalendarMutationCommand =
  { acknowledge: boolean; type: "commitment" } | { type: "event" };

export function initialOccurrenceDraft(item: CalendarOccurrence): CalendarOccurrenceDraft {
  return {
    action: null,
    endsAt: localInput(new Date(item.endsAt)),
    notes: item.notes ?? "Protected calendar detail.",
    reason: "",
    startsAt: localInput(new Date(item.startsAt)),
    title: item.title,
    until: localInput(new Date(new Date(item.startsAt).getTime() + 7 * 86_400_000)),
  };
}

export async function executeCalendarMutation(
  command: CalendarMutationCommand,
  draft: CalendarOccurrenceDraft,
  item: CalendarOccurrence,
  csrfToken: string,
) {
  if (command.type === "commitment") {
    return api.decideCalendarCommitment(
      item.eventId,
      {
        expectedVersion: item.version,
        reason: command.acknowledge ? null : draft.reason,
      },
      command.acknowledge,
      csrfToken,
    );
  }
  if (draft.action === "cancel-series") {
    return api.cancelCalendarEvent(item.eventId, cancellationInput(draft, item), csrfToken);
  }
  if (draft.action === "cancel-occurrence") {
    return api.cancelCalendarOccurrence(item.eventId, cancellationInput(draft, item), csrfToken);
  }
  if (draft.action === "edit") {
    return api.editCalendarOccurrence(item.eventId, editInput(draft, item), csrfToken);
  }
  if (draft.action === "split") {
    return api.splitCalendarSeries(item.eventId, splitInput(draft, item), csrfToken);
  }
  throw new Error("Select a calendar action.");
}

function cancellationInput(draft: CalendarOccurrenceDraft, item: CalendarOccurrence) {
  return {
    expectedVersion: item.version,
    occurrenceStart: item.occurrenceStart,
    reason: draft.reason,
  };
}

function editInput(draft: CalendarOccurrenceDraft, item: CalendarOccurrence) {
  return {
    expectedVersion: item.version,
    notes: draft.notes,
    occurrenceStart: item.occurrenceStart,
    reason: draft.reason,
    replacementEnd: new Date(draft.endsAt).toISOString(),
    replacementStart: new Date(draft.startsAt).toISOString(),
    title: draft.title,
  };
}

function splitInput(draft: CalendarOccurrenceDraft, item: CalendarOccurrence) {
  return {
    allDay: item.allDay,
    category: item.category,
    endsAt: new Date(draft.endsAt).toISOString(),
    expectedVersion: item.version,
    notes: draft.notes,
    reason: draft.reason,
    recurrence: item.recurrence,
    recurrenceInterval: 1,
    recurrenceUntil: new Date(draft.until).toISOString(),
    splitFrom: item.occurrenceStart,
    startsAt: new Date(draft.startsAt).toISOString(),
    timeZone: item.timeZone,
    title: draft.title,
    visibility: item.visibility,
  };
}
