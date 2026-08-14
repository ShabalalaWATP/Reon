import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { boardApi } from "../../lib/api/boardClient";
import type { BoardColumn, BoardFilters } from "../../lib/api/boardTypes";
import type { CalendarOccurrence } from "../../lib/api/calendarTypes";
import { api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { TeamActivity, TeamMember } from "../../lib/api/teamTypes";
import type { Session, WorkItem } from "../../lib/api/types";
import { addLocalDays } from "../../lib/dateInputs";

const requestBoardFilters: Partial<BoardFilters> = { itemTypes: ["SERVICE_REQUEST"] };

export type DeliveryHomeData = {
  activity: TeamActivity[];
  activityEmpty: boolean;
  activityError: boolean;
  boardError: boolean;
  calendarError: boolean;
  calendarPending: boolean;
  counts?: Record<BoardColumn, number>;
  currentPeople: TeamMember[];
  peopleError: boolean;
  upcoming: CalendarOccurrence[];
};

export type RoutingHomeData = {
  activity: TeamActivity[];
  activityEmpty: boolean;
  activityError: boolean;
  availableCount: number;
  calendarError: boolean;
  calendarPending: boolean;
  informationCount: number;
  mineCount: number;
  oldestCreatedAt?: string;
  queueError: boolean;
  stages: Array<[string, number]>;
  upcoming: CalendarOccurrence[];
};

export function useDeliveryTeamHomeData(teamId: string, session: Session): DeliveryHomeData {
  const queryKeys = protectedQueryKeys(session);
  const [calendarFrom, calendarTo] = useCalendarRange();
  const board = useQuery({
    queryKey: queryKeys.teamBoard(teamId, "home-requests"),
    queryFn: () => boardApi.board(teamId, requestBoardFilters, { limit: 8 }),
  });
  const people = useQuery({
    queryKey: queryKeys.teamPeople(teamId),
    queryFn: () => api.teamPeople(teamId),
  });
  const calendar = useQuery({
    queryKey: queryKeys.teamCalendar(teamId, calendarFrom, calendarTo),
    queryFn: () => api.teamCalendar(teamId, calendarFrom, calendarTo),
  });
  const activity = useQuery({
    queryKey: queryKeys.teamActivity(teamId),
    queryFn: () => api.teamActivity(teamId),
  });
  return {
    activity: activity.data?.items.slice(0, 5) ?? [],
    activityEmpty: !activity.isPending && activity.data?.items.length === 0,
    activityError: activity.isError,
    boardError: board.isError,
    calendarError: calendar.isError,
    calendarPending: calendar.isPending,
    counts: board.data?.columnCounts,
    currentPeople: people.data?.items.filter((item) => item.state === "CURRENT") ?? [],
    peopleError: people.isError,
    upcoming: calendar.data?.items.slice(0, 5) ?? [],
  };
}

export function useRoutingTeamHomeData(teamId: string, session: Session): RoutingHomeData {
  const queryKeys = protectedQueryKeys(session);
  const [from, to] = useCalendarRange();
  const queue = useQuery({
    queryKey: queryKeys.workItems(teamId),
    queryFn: () => api.workItems(undefined, teamId),
  });
  const calendar = useQuery({
    queryKey: queryKeys.teamCalendar(teamId, from, to),
    queryFn: () => api.teamCalendar(teamId, from, to),
  });
  const activity = useQuery({
    queryKey: queryKeys.teamActivity(teamId),
    queryFn: () => api.teamActivity(teamId),
  });
  const items = queue.data?.items ?? [];
  const oldest = [...items].sort((left, right) => left.createdAt.localeCompare(right.createdAt))[0];
  return {
    activity: activity.data?.items.slice(0, 5) ?? [],
    activityEmpty: !activity.isPending && activity.data?.items.length === 0,
    activityError: activity.isError,
    availableCount: items.filter((item) => !item.assigneeId).length,
    calendarError: calendar.isError,
    calendarPending: calendar.isPending,
    informationCount: items.filter((item) => item.stage.includes("INFORMATION")).length,
    mineCount: items.filter((item) => item.assigneeId === session.user.id).length,
    oldestCreatedAt: oldest?.createdAt,
    queueError: queue.isError,
    stages: stageCounts(items),
    upcoming: calendar.data?.items.slice(0, 5) ?? [],
  };
}

function useCalendarRange() {
  return useMemo(() => {
    const now = new Date();
    return [now.toISOString(), addLocalDays(now, 14).toISOString()] as const;
  }, []);
}

function stageCounts(items: WorkItem[]): Array<[string, number]> {
  const counts = new Map<string, number>();
  items.forEach((item) => counts.set(item.stage, (counts.get(item.stage) ?? 0) + 1));
  return [...counts.entries()].sort((left, right) => right[1] - left[1]);
}
