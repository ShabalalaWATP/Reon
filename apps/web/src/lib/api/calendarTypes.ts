export type CalendarCategory =
  "AVAILABILITY" | "SERVICE_WORK" | "LEAVE" | "TRAINING" | "DUTY" | "APPOINTMENT" | "OTHER";
export type CalendarVisibility = "PRIVATE" | "AVAILABILITY_ONLY" | "TEAM_DETAIL";
export type RecurrenceFrequency = "NONE" | "DAILY" | "WEEKLY";
export type CalendarEventKind = "PERSONAL" | "TEAM" | "COMMITMENT";
export type CommitmentStatus = "NOT_REQUIRED" | "PENDING" | "ACKNOWLEDGED" | "DISPUTED";

export interface CalendarOccurrence {
  eventId: string;
  occurrenceStart: string;
  startsAt: string;
  endsAt: string;
  title: string;
  notes: string | null;
  category: CalendarCategory;
  visibility: CalendarVisibility;
  kind: CalendarEventKind;
  subjectUserId: string;
  subjectDisplayName: string;
  teamId: string | null;
  requestId?: string | null;
  allDay: boolean;
  timeZone: string;
  recurrence: RecurrenceFrequency;
  commitmentStatus: CommitmentStatus;
  version: number;
  isException: boolean;
}

export interface CalendarEventInput {
  title: string;
  notes: string;
  startsAt: string;
  endsAt: string;
  timeZone: string;
  allDay: boolean;
  category: CalendarCategory;
  visibility: CalendarVisibility;
  recurrence: RecurrenceFrequency;
  recurrenceInterval: number;
  recurrenceUntil: string | null;
}

export interface CalendarEventResult {
  eventId: string;
  version: number;
}
export interface TeamCalendarEventInput extends CalendarEventInput {
  grantId: string;
}
export interface CommitmentInput extends TeamCalendarEventInput {
  subjectUserId: string;
  requestId: string;
}
export interface CalendarEventUpdateInput extends CalendarEventInput {
  expectedVersion: number;
}
export interface OccurrenceCancelInput {
  expectedVersion: number;
  occurrenceStart: string;
  reason: string;
}
export interface OccurrenceEditInput extends OccurrenceCancelInput {
  title: string;
  notes: string;
  replacementStart: string;
  replacementEnd: string;
}
export interface FutureSplitInput extends CalendarEventInput {
  expectedVersion: number;
  splitFrom: string;
  reason: string;
}
export interface CommitmentDecisionInput {
  expectedVersion: number;
  reason: string | null;
}
export interface CapacityPreviewInput {
  grantId: string;
  dateFrom: string;
  dateTo: string;
  timeZone: string;
}
export interface CapacityCommitInput {
  grantId: string;
  token: string;
}
export interface CapacityDay {
  date: string;
  memberCount: number;
  baselineMinutes: number;
  unavailableMinutes: number;
  availableMinutes: number;
}
export interface CapacityPreview {
  token: string;
  expiresAt: string;
  days: CapacityDay[];
}
export interface CapacitySnapshot {
  snapshotId: string;
  days: CapacityDay[];
}
