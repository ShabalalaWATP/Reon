import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router";

import { api } from "../../lib/api/client";
import type { CalendarOccurrence } from "../../lib/api/calendarTypes";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import { useAuth } from "../../lib/auth/AuthProvider";
import { calendarRange, moveAnchor, type CalendarView } from "./calendarDates";

export const validCalendarViews: CalendarView[] = ["month", "week", "agenda"];

export function useCalendarPage(access?: TeamWorkspaceAccess) {
  const { session } = useAuth();
  const queryKeys = protectedQueryKeys(session);
  const params = useParams();
  const [view, setView] = useState<CalendarView>(() => normaliseCalendarView(params.calendarView));
  const [anchor, setAnchor] = useState(() => new Date());
  const [selected, setSelected] = useState<CalendarOccurrence | null>(null);
  const [draftDate, setDraftDate] = useState<Date | null>(null);
  const [creating, setCreating] = useState(false);
  const range = calendarRange(anchor, view);
  const queryKey = access
    ? queryKeys.teamCalendar(access.teamId, range.from, range.to)
    : queryKeys.personalCalendar(range.from, range.to);
  const calendar = useQuery({
    queryKey,
    queryFn: () => loadCalendar(access, range),
  });
  const workspaces = useQuery({
    queryKey: queryKeys.teamWorkspaces(),
    queryFn: api.teamWorkspaces,
    enabled: !access,
  });
  const { canManage, canReadPeople } = calendarPageAccess(access);
  const people = useQuery({
    queryKey: queryKeys.teamPeople(access?.teamId),
    queryFn: () => api.teamPeople(access?.teamId ?? ""),
    enabled: canManage && canReadPeople,
  });
  const personalWorkspace = workspaces.data?.items[0];

  return {
    access,
    anchor,
    calendar,
    canManage,
    closeCreate: () => setCreating(false),
    closeSelected: () => setSelected(null),
    creating,
    draftDate,
    move: (direction: -1 | 1) => setAnchor((current) => moveAnchor(current, view, direction)),
    openCreate: (day: Date) => {
      setDraftDate(day);
      setCreating(true);
    },
    people: people.data?.items,
    personalWorkspace,
    queryKey,
    range,
    selected,
    selectOccurrence: setSelected,
    setToday: () => setAnchor(new Date()),
    setView,
    sharingUnitName: access?.teamName ?? personalWorkspace?.teamName,
    view,
  };
}

function calendarPageAccess(access: TeamWorkspaceAccess | undefined) {
  return {
    canManage: Boolean(access?.grantId && access.permissions.includes("CALENDAR")),
    canReadPeople: !access?.views || access.views.includes("PEOPLE"),
  };
}

function loadCalendar(
  access: TeamWorkspaceAccess | undefined,
  range: { from: string; to: string },
) {
  return access
    ? api.teamCalendar(access.teamId, range.from, range.to)
    : api.personalCalendar(range.from, range.to);
}

function normaliseCalendarView(value: string | undefined): CalendarView {
  const candidate = value as CalendarView;
  return validCalendarViews.includes(candidate) ? candidate : "month";
}
