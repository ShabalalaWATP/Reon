import type { CalendarOccurrence } from "../../lib/api/calendarTypes";
import type { Session } from "../../lib/api/types";
import type { TeamMember, TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import { requesterSession } from "../../test/fixtures";
import { json, mockFetch } from "../../test/render";

export const managerSession: Session = {
  ...requesterSession,
  user: {
    ...requesterSession.user,
    id: "manager-ssg",
    username: "admin8",
    displayName: "Grant Hanley",
    role: "DELIVERY_TEAM_LEAD",
    scope: "SSG Team",
  },
};

export const analystSession: Session = {
  ...managerSession,
  user: {
    ...managerSession.user,
    id: "analyst-ssg",
    username: "admin11",
    displayName: "Lewis Ferguson",
    role: "DELIVERY_SPECIALIST",
  },
};

export const staffWithoutWorkspace: Session = {
  ...managerSession,
  user: {
    ...managerSession.user,
    id: "routing-member",
    username: "admin75",
    displayName: "Willie Ormond",
    role: "INTAKE_TRIAGE",
    scope: "CRIOC",
  },
};

export const managerAccess: TeamWorkspaceAccess = {
  teamId: "team-ssg",
  teamCode: "SSG_TEAM",
  teamName: "SSG Team",
  unitKind: "TEAM",
  workspacePosition: "MANAGER",
  grantId: "grant-ssg",
  permissions: ["CALENDAR", "CAPACITY", "ROSTER"],
};

export const analystAccess: TeamWorkspaceAccess = {
  ...managerAccess,
  grantId: null,
  permissions: [],
};

const people: TeamMember[] = [
  {
    membershipId: "membership-manager",
    accountId: "manager-ssg",
    displayName: "Grant Hanley",
    role: "DELIVERY_TEAM_LEAD",
    state: "CURRENT",
    effectiveFrom: "2026-01-01T09:00:00Z",
    effectiveUntil: null,
    version: 1,
    activeWorkCount: 0,
    skills: ["Delivery leadership"],
    startReason: null,
    endReason: null,
  },
  {
    membershipId: "membership-analyst",
    accountId: "analyst-ssg",
    displayName: "Lewis Ferguson",
    role: "DELIVERY_SPECIALIST",
    state: "CURRENT",
    effectiveFrom: "2026-01-01T09:00:00Z",
    effectiveUntil: null,
    version: 1,
    activeWorkCount: 0,
    skills: ["Research"],
    startReason: null,
    endReason: null,
  },
];

export function occurrence(overrides: Partial<CalendarOccurrence> = {}): CalendarOccurrence {
  const startsAt = tomorrow(9);
  return {
    eventId: "event-personal",
    occurrenceStart: startsAt,
    startsAt,
    endsAt: tomorrow(11),
    title: "Protected planning time",
    notes: "Synthetic private planning detail.",
    category: "TRAINING",
    visibility: "PRIVATE",
    kind: "PERSONAL",
    subjectUserId: "analyst-ssg",
    subjectDisplayName: "Lewis Ferguson",
    teamId: null,
    allDay: false,
    timeZone: "Europe/London",
    recurrence: "DAILY",
    commitmentStatus: "NOT_REQUIRED",
    version: 1,
    isException: false,
    ...overrides,
  };
}

export function mockCalendar(
  session: Session,
  access: TeamWorkspaceAccess,
  items: CalendarOccurrence[],
  calls: Array<{ path: string; body: Record<string, unknown> }>,
  options: {
    boardFailure?: boolean;
    calendarFailures?: number;
    mutationFailure?: string;
    noWorkspace?: boolean;
    workspaceFailure?: boolean;
  } = {},
) {
  const state = { calendarReads: 0 };
  return mockFetch(
    async (url, init) =>
      handleCalendarRequest(url, init, { access, calls, items, options, session, state }),
    true,
    true,
    false,
  );
}

type CalendarMockContext = {
  access: TeamWorkspaceAccess;
  calls: Array<{ path: string; body: Record<string, unknown> }>;
  items: CalendarOccurrence[];
  options: {
    boardFailure?: boolean;
    calendarFailures?: number;
    mutationFailure?: string;
    noWorkspace?: boolean;
    workspaceFailure?: boolean;
  };
  session: Session;
  state: { calendarReads: number };
};

function handleCalendarRequest(url: URL, init: RequestInit, context: CalendarMockContext) {
  if (init.method && init.method !== "GET") return calendarMutationResponse(url, init, context);
  return calendarReadResponse(url, context);
}

function calendarReadResponse(url: URL, context: CalendarMockContext) {
  if (url.pathname.endsWith("/auth/me")) return json(context.session);
  if (url.pathname.endsWith("/team-workspaces"))
    return context.options.workspaceFailure
      ? json({ detail: "Synthetic workspace failure" }, 503)
      : json({ items: context.options.noWorkspace ? [] : [context.access] });
  if (url.pathname.endsWith("/people")) return json({ items: people });
  if (url.pathname.endsWith("/board")) return boardResponse(context.options.boardFailure);
  if (url.pathname.endsWith("/calendar/personal") || url.pathname.endsWith("/calendar")) {
    context.state.calendarReads += 1;
    if (context.state.calendarReads <= (context.options.calendarFailures ?? 0))
      return json({ detail: "Synthetic calendar read failure" }, 503);
    return json({ items: context.items });
  }
  throw new Error(`Unexpected ${url.pathname}`);
}

function calendarMutationResponse(url: URL, init: RequestInit, context: CalendarMockContext) {
  const body = JSON.parse(String(init.body)) as Record<string, unknown>;
  context.calls.push({ path: url.pathname, body });
  if (context.options.mutationFailure && url.pathname.endsWith(context.options.mutationFailure))
    return json({ detail: "Synthetic calendar conflict" }, 409);
  if (url.pathname.endsWith("/capacity/previews")) return capacityPreview();
  if (url.pathname.endsWith("/capacity/commits")) return json({ snapshotId: "snapshot", days: [] });
  return json({ eventId: "event-result", version: 2 });
}

function boardResponse(failed?: boolean) {
  if (failed) return json({ detail: "Synthetic board failure" }, 503);
  return json({
    items: [
      {
        id: "request-one",
        itemType: "SERVICE_REQUEST",
        reference: "REQ-001",
        title: "Synthetic current request",
        column: "IN_PROGRESS",
        priority: "MEDIUM",
        dueOn: tomorrow(16),
        ownerUserId: "analyst-ssg",
        ownerDisplayName: "Lewis Ferguson",
        version: 1,
        linkedRequestId: null,
        availableColumns: ["IN_PROGRESS"],
        changedAt: "2026-08-07T10:00:00Z",
      },
    ],
    nextCursor: null,
    columnCounts: {},
    totalCount: 1,
    wipLimits: {},
    configurationVersion: 1,
    savedViews: [],
    generatedAt: new Date().toISOString(),
  });
}

function capacityPreview() {
  return json({
    token: "preview-token-value-that-is-long-enough",
    expiresAt: tomorrow(12),
    days: [
      {
        date: new Date().toISOString().slice(0, 10),
        memberCount: 2,
        baselineMinutes: 900,
        unavailableMinutes: 120,
        availableMinutes: 780,
      },
    ],
  });
}

export function tomorrow(hour: number) {
  const value = new Date();
  value.setDate(value.getDate() + 1);
  value.setHours(hour, 0, 0, 0);
  return value.toISOString();
}

export function localTomorrow(hour: number) {
  const value = new Date(tomorrow(hour));
  return new Date(value.getTime() - value.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}
