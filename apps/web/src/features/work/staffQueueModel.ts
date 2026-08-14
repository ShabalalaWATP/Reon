import type { InfiniteData } from "@tanstack/react-query";

import type { ListResponse, WorkItem } from "../../lib/api/types";
import type { WorkActionName } from "./workActionModel";

export type SelectedQueueAction = {
  action: WorkActionName;
  workItemId: string;
};

export function selectedWorkItem(items: WorkItem[], selectedId: string | null) {
  return items.find((item) => item.id === selectedId) ?? items[0];
}

export function activeWorkAction(
  item: WorkItem | undefined,
  selection: SelectedQueueAction | null,
) {
  if (!item) return undefined;
  if (selection?.workItemId === item.id && item.availableActions.includes(selection.action))
    return selection.action;
  return item.availableActions[0];
}

export function isAssignedToUser(item: WorkItem | undefined, userId?: string) {
  return Boolean(item && userId && (item.assignedToCurrentUser || item.assigneeId === userId));
}

export function removeWorkItem(
  current: InfiniteData<ListResponse<WorkItem>, string | null> | undefined,
  workItemId: string,
) {
  if (!current) return current;
  return {
    ...current,
    pages: current.pages.map((page) => ({
      ...page,
      items: page.items.filter((item) => item.id !== workItemId),
    })),
  };
}

export function requestFilter(searchParams: URLSearchParams) {
  return searchParams.get("requestId")?.trim() || undefined;
}
