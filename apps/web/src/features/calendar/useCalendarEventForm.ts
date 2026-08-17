import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api } from "../../lib/api/client";
import { boardApi } from "../../lib/api/boardClient";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { TeamMember, TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import { useAuth } from "../../lib/auth/AuthProvider";
import {
  calendarEventInput,
  clearedCalendarEventDraft,
  currentAnalysts,
  draftForDate,
  initialCalendarEventDraft,
  type CalendarEventDraft,
  type CalendarEventMode,
} from "./calendarEventModel";

type CalendarEventFormOptions = {
  access?: TeamWorkspaceAccess;
  initialDate?: Date | null;
  members?: TeamMember[];
  onCreated?: () => void;
  range: { from: string; to: string };
};

export function useCalendarEventForm(options: CalendarEventFormOptions) {
  const { access, initialDate, members, onCreated, range } = options;
  const { session } = useAuth();
  const queryKeys = protectedQueryKeys(session);
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState(initialCalendarEventDraft);
  const { canManage, ticketCommitments } = calendarFormAccess(access);
  const requests = useQuery({
    queryKey: queryKeys.teamBoard(access?.teamId ?? "", "calendar-commitments"),
    queryFn: () =>
      boardApi.board(access?.teamId ?? "", { itemTypes: ["SERVICE_REQUEST"] }, { limit: 100 }),
    enabled: Boolean(access && ticketCommitments && draft.mode === "commitment"),
  });

  useEffect(() => {
    if (initialDate) {
      setDraft((current) => draftForDate(current, initialDate));
    }
  }, [initialDate]);

  const mutation = useMutation({
    mutationFn: () => createEvent(draft, access, session),
    onSuccess: () => {
      setDraft((current) => clearedCalendarEventDraft(current));
      void queryClient.invalidateQueries({
        queryKey: access
          ? queryKeys.teamCalendar(access.teamId, range.from, range.to)
          : queryKeys.personalCalendar(range.from, range.to),
      });
      onCreated?.();
    },
  });

  const update = <Key extends keyof CalendarEventDraft>(key: Key, value: CalendarEventDraft[Key]) =>
    setDraft((current) => ({ ...current, [key]: value }));
  const selectMode = (mode: CalendarEventMode) =>
    setDraft((current) => ({
      ...current,
      mode,
      visibility: "TEAM_DETAIL",
    }));

  return {
    analysts: currentAnalysts(members),
    canManage,
    draft,
    mutation,
    requests,
    selectMode,
    submit: () => mutation.mutate(),
    ticketCommitments,
    update,
  };
}

function calendarFormAccess(access: TeamWorkspaceAccess | undefined) {
  const canManage = Boolean(access?.grantId && access.permissions.includes("CALENDAR"));
  const canReadBoard = !access?.views || access.views.includes("BOARD");
  const canReadPeople = !access?.views || access.views.includes("PEOPLE");
  return {
    canManage,
    ticketCommitments: canManage && canReadBoard && canReadPeople && access?.unitKind === "TEAM",
  };
}

async function createEvent(
  draft: CalendarEventDraft,
  access: TeamWorkspaceAccess | undefined,
  session: ReturnType<typeof useAuth>["session"],
) {
  if (!session) throw new Error("Sign in is required.");
  const input = calendarEventInput(draft);
  if (!access || draft.mode === "personal") {
    return api.createPersonalCalendarEvent(input, session.csrfToken);
  }
  if (!access.grantId) {
    throw new Error("Calendar management authority is required.");
  }
  if (draft.mode === "commitment") {
    if (!draft.subjectId || !draft.requestId) {
      throw new Error("Select a request and an Analyst.");
    }
    return api.createCalendarCommitment(
      access.teamId,
      {
        ...input,
        grantId: access.grantId,
        requestId: draft.requestId,
        subjectUserId: draft.subjectId,
      },
      session.csrfToken,
    );
  }
  return api.createTeamCalendarEvent(
    access.teamId,
    { ...input, grantId: access.grantId },
    session.csrfToken,
  );
}
