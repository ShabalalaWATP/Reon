import {
  type InfiniteData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router";

import { api } from "../../lib/api/client";
import { flattenUniquePages } from "../../lib/api/pagination";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type {
  EligibleSpecialist,
  ListResponse,
  RoutingOptionsWorkspace,
  WorkAction,
  WorkItem,
} from "../../lib/api/types";
import { useAuth } from "../../lib/auth/AuthProvider";
import type { SpecialistOptions } from "./EligibleSpecialistField";
import type { RoutingOptions } from "./RoutingDestinationField";
import {
  activeWorkAction,
  isAssignedToUser,
  removeWorkItem,
  requestFilter,
  selectedWorkItem,
  type SelectedQueueAction,
} from "./staffQueueModel";
import { actionRequiresDestination } from "./workActionModel";

export function useStaffQueueController(teamId?: string) {
  const { session } = useAuth();
  const [searchParams] = useSearchParams();
  const requestId = requestFilter(searchParams);
  const queryKeys = protectedQueryKeys(session);
  const queueQueryKey = queryKeys.workItemPages(teamId, requestId);
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedAction, setSelectedAction] = useState<SelectedQueueAction | null>(null);
  const listQuery = useInfiniteQuery({
    queryKey: queueQueryKey,
    queryFn: ({ pageParam }) => api.workItems(pageParam ?? undefined, teamId, requestId),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.nextCursor ?? undefined,
    enabled: Boolean(session),
    refetchInterval: 30_000,
  });
  const items = listQuery.data ? flattenUniquePages(listQuery.data.pages) : [];
  const selected = selectedWorkItem(items, selectedId);
  const activeAction = activeWorkAction(selected, selectedAction);
  const selectedIsAssigned = isAssignedToUser(selected, session?.user.id);
  const loadSpecialists = Boolean(
    selected?.stage === "DELIVERY_PLANNING" && selectedIsAssigned && activeAction === "assign",
  );
  const loadRouting = selectedIsAssigned && actionRequiresDestination(activeAction);
  const specialists = useQuery({
    queryKey: queryKeys.eligibleSpecialists(selected?.id),
    queryFn: () => api.eligibleSpecialists(requireSelected(selected).id),
    enabled: loadSpecialists,
  });
  const routing = useQuery({
    queryKey: queryKeys.routingOptions(selected?.id),
    queryFn: () => api.routingOptions(requireSelected(selected).id),
    enabled: loadRouting,
  });
  const detail = useQuery({
    queryKey: queryKeys.request(selected?.requestId),
    queryFn: () => api.request(requireSelected(selected).requestId),
    enabled: selectedIsAssigned,
  });
  const claim = useMutation({
    mutationFn: (item: WorkItem) =>
      api.claimWorkItem(item.id, requireSessionToken(session?.csrfToken)),
    onSuccess: async (_result, item) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.workItems() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.request(item.requestId) }),
      ]);
    },
  });
  const complete = useMutation({
    mutationFn: ({ action, item }: { action: WorkAction; item: WorkItem }) =>
      api.completeWorkItem(item.id, action, requireSessionToken(session?.csrfToken)),
    onSuccess: (_result, { item }) => {
      setSelectedId(null);
      setSelectedAction(null);
      queryClient.setQueryData<InfiniteData<ListResponse<WorkItem>, string | null>>(
        queueQueryKey,
        (current) => removeWorkItem(current, item.id),
      );
      queryClient.removeQueries({ queryKey: queryKeys.request(item.requestId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.workItems() });
    },
  });
  return {
    activeAction,
    canLoadDetail: selectedIsAssigned,
    claim,
    complete,
    detail,
    items,
    listQuery,
    mutationError: claim.error ?? complete.error,
    requestId,
    routingOptions: routingState(routing, loadRouting),
    selected,
    selectAction: (action: SelectedQueueAction) => setSelectedAction(action),
    selectItem: setSelectedId,
    session,
    specialistOptions: specialistState(specialists, loadSpecialists),
  };
}

function specialistState(
  query: QueryState<{ items: EligibleSpecialist[] }>,
  enabled: boolean,
): SpecialistOptions {
  const onRetry = () => void query.refetch();
  if (!enabled) return { items: [], onRetry, status: "idle" };
  if (query.isPending) return { items: [], onRetry, status: "loading" };
  if (query.isError) return { items: [], onRetry, status: "error" };
  if (!query.data) return { items: [], onRetry, status: "error" };
  return { items: query.data.items, onRetry, status: "ready" };
}

function routingState(
  query: QueryState<RoutingOptionsWorkspace>,
  enabled: boolean,
): RoutingOptions {
  const onRetry = () => void query.refetch();
  if (!enabled) return { items: [], onRetry, status: "idle" };
  if (query.isPending) return { items: [], onRetry, status: "loading" };
  if (query.isError) return { items: [], onRetry, status: "error" };
  if (!query.data) return { items: [], onRetry, status: "error" };
  return {
    items: query.data.items,
    onRetry,
    route: query.data.route,
    status: "ready",
  };
}

function requireSelected(item: WorkItem | undefined) {
  if (!item) throw new Error("A work item must be selected.");
  return item;
}

function requireSessionToken(token?: string) {
  if (!token) throw new Error("Sign in is required.");
  return token;
}

type QueryState<T> = {
  data: T | undefined;
  isError: boolean;
  isPending: boolean;
  refetch: () => Promise<unknown>;
};
