import type {
  CalendarEventInput,
  CalendarEventResult,
  CalendarEventUpdateInput,
  CalendarOccurrence,
  CapacityCommitInput,
  CapacityPreview,
  CapacityPreviewInput,
  CapacitySnapshot,
  CommitmentDecisionInput,
  CommitmentInput,
  FutureSplitInput,
  OccurrenceCancelInput,
  OccurrenceEditInput,
  TeamCalendarEventInput,
} from "./calendarTypes";
import { apiRequest } from "./transport";

export const calendarApi = {
  personalCalendar: (from: string, to: string) => {
    const query = new URLSearchParams({ from, to });
    return apiRequest<{ items: CalendarOccurrence[] }>(`/calendar/personal?${query.toString()}`);
  },
  teamCalendar: (teamId: string, from: string, to: string) => {
    const query = new URLSearchParams({ from, to });
    return apiRequest<{ items: CalendarOccurrence[] }>(`/team-workspaces/${encodeURIComponent(teamId)}/calendar?${query.toString()}`);
  },
  createPersonalCalendarEvent: (input: CalendarEventInput, csrfToken: string) =>
    apiRequest<CalendarEventResult>("/calendar/events", { body: input, csrfToken, method: "POST" }),
  createTeamCalendarEvent: (teamId: string, input: TeamCalendarEventInput, csrfToken: string) =>
    apiRequest<CalendarEventResult>(`/team-workspaces/${encodeURIComponent(teamId)}/calendar/events`, { body: input, csrfToken, method: "POST" }),
  createCalendarCommitment: (teamId: string, input: CommitmentInput, csrfToken: string) =>
    apiRequest<CalendarEventResult>(`/team-workspaces/${encodeURIComponent(teamId)}/calendar/commitments`, { body: input, csrfToken, method: "POST" }),
  updateCalendarEvent: (eventId: string, input: CalendarEventUpdateInput, csrfToken: string) =>
    apiRequest<CalendarEventResult>(`/calendar/events/${encodeURIComponent(eventId)}`, { body: input, csrfToken, method: "PUT" }),
  cancelCalendarEvent: (eventId: string, input: OccurrenceCancelInput, csrfToken: string) =>
    apiRequest<CalendarEventResult>(`/calendar/events/${encodeURIComponent(eventId)}/cancel`, { body: input, csrfToken, method: "POST" }),
  cancelCalendarOccurrence: (eventId: string, input: OccurrenceCancelInput, csrfToken: string) =>
    apiRequest<CalendarEventResult>(`/calendar/events/${encodeURIComponent(eventId)}/occurrences/cancel`, { body: input, csrfToken, method: "POST" }),
  editCalendarOccurrence: (eventId: string, input: OccurrenceEditInput, csrfToken: string) =>
    apiRequest<CalendarEventResult>(`/calendar/events/${encodeURIComponent(eventId)}/occurrences/edit`, { body: input, csrfToken, method: "POST" }),
  splitCalendarSeries: (eventId: string, input: FutureSplitInput, csrfToken: string) =>
    apiRequest<CalendarEventResult>(`/calendar/events/${encodeURIComponent(eventId)}/split`, { body: input, csrfToken, method: "POST" }),
  decideCalendarCommitment: (eventId: string, input: CommitmentDecisionInput, acknowledge: boolean, csrfToken: string) =>
    apiRequest<CalendarEventResult>(`/calendar/events/${encodeURIComponent(eventId)}/${acknowledge ? "acknowledge" : "dispute"}`, { body: input, csrfToken, method: "POST" }),
  previewTeamCapacity: (teamId: string, input: CapacityPreviewInput, csrfToken: string) =>
    apiRequest<CapacityPreview>(`/team-workspaces/${encodeURIComponent(teamId)}/capacity/previews`, { body: input, csrfToken, method: "POST" }),
  commitTeamCapacity: (teamId: string, input: CapacityCommitInput, csrfToken: string) =>
    apiRequest<CapacitySnapshot>(`/team-workspaces/${encodeURIComponent(teamId)}/capacity/commits`, { body: input, csrfToken, method: "POST" }),
};
