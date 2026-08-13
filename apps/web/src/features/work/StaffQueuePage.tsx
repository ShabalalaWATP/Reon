import {
  type InfiniteData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { ClipboardList } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router";

import { PageState } from "../../components/PageState";
import { api, ApiError } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import { flattenUniquePages } from "../../lib/api/pagination";
import type { ListResponse, WorkAction, WorkItem } from "../../lib/api/types";
import { useAuth } from "../../lib/auth/AuthProvider";
import { queueLabelForRole, roleRoutes } from "../../lib/routes";
import type { SpecialistOptions } from "./EligibleSpecialistField";
import type { RoutingOptions } from "./RoutingDestinationField";
import { WorkQueueDetail } from "./WorkQueueDetail";
import { WorkQueueList } from "./WorkQueueList";
import {
  actionRequiresDestination,
  type WorkActionName,
} from "./workActionModel";

type StaffQueuePageProps = {
  description: string;
  embedded?: boolean;
  eyebrow: string;
  teamId?: string;
  title: string;
};

export function StaffQueuePage({
  description,
  embedded = false,
  eyebrow,
  teamId,
  title,
}: StaffQueuePageProps) {
  const { session } = useAuth();
  const [searchParams] = useSearchParams();
  const requestId = searchParams.get("requestId")?.trim() || undefined;
  const userId = session?.user.id ?? "anonymous";
  const queueQueryKey = protectedQueryKeys.workItems(
    userId,
    teamId,
    requestId,
  );
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedAction, setSelectedAction] = useState<{
    action: WorkActionName;
    workItemId: string;
  } | null>(null);
  const listQuery = useInfiniteQuery({
    queryKey: queueQueryKey,
    queryFn: ({ pageParam }) =>
      api.workItems(pageParam ?? undefined, teamId, requestId),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.nextCursor ?? undefined,
    enabled: Boolean(session),
    refetchInterval: 30_000,
  });
  const items = listQuery.data
    ? flattenUniquePages(listQuery.data.pages)
    : [];
  const selected = items.find((item) => item.id === selectedId) ?? items[0];
  const activeAction =
    selected &&
    selectedAction?.workItemId === selected.id &&
    selected.availableActions.includes(selectedAction.action)
      ? selectedAction.action
      : selected?.availableActions[0];
  const selectedIsAssigned = Boolean(
    selected && session && (
      selected.assignedToCurrentUser || selected.assigneeId === session.user.id
    ),
  );
  const shouldLoadEligibleSpecialists = Boolean(
    selected &&
    session &&
    selected.stage === "DELIVERY_PLANNING" &&
    selectedIsAssigned &&
    activeAction === "assign",
  );
  const eligibleSpecialistsQuery = useQuery({
    queryKey: protectedQueryKeys.eligibleSpecialists(userId, selected?.id),
    queryFn: () => api.eligibleSpecialists(selected!.id),
    enabled: shouldLoadEligibleSpecialists,
  });
  const shouldLoadRoutingOptions = Boolean(
    selected &&
    session &&
    selectedIsAssigned &&
    actionRequiresDestination(activeAction),
  );
  const canLoadDetail = Boolean(
    selectedIsAssigned,
  );
  const routingOptionsQuery = useQuery({
    queryKey: protectedQueryKeys.routingOptions(userId, selected?.id),
    queryFn: () => api.routingOptions(selected!.id),
    enabled: shouldLoadRoutingOptions,
  });
  const detailQuery = useQuery({
    queryKey: protectedQueryKeys.request(userId, selected?.requestId),
    queryFn: () => api.request(selected!.requestId),
    enabled: canLoadDetail,
  });

  const refreshAfterClaim = async (item: WorkItem) => {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: protectedQueryKeys.workItems(userId),
      }),
      queryClient.invalidateQueries({
        queryKey: protectedQueryKeys.request(userId, item.requestId),
      }),
    ]);
  };
  const claim = useMutation({
    mutationFn: (item: WorkItem) =>
      api.claimWorkItem(item.id, session!.csrfToken),
    onSuccess: refreshAfterClaim,
  });
  const complete = useMutation({
    mutationFn: ({ action, item }: { action: WorkAction; item: WorkItem }) =>
      api.completeWorkItem(item.id, action, session!.csrfToken),
    onSuccess: (_request, variables) => {
      setSelectedId(null);
      setSelectedAction(null);
      queryClient.setQueryData<
        InfiniteData<ListResponse<WorkItem>, string | null>
      >(queueQueryKey, (current) =>
        current
          ? {
              ...current,
              pages: current.pages.map((page) => ({
                ...page,
                items: page.items.filter(
                  (item) => item.id !== variables.item.id,
                ),
              })),
            }
          : current,
      );
      queryClient.removeQueries({
        queryKey: protectedQueryKeys.request(userId, variables.item.requestId),
      });
      void queryClient.invalidateQueries({
        queryKey: protectedQueryKeys.workItems(userId),
      });
    },
  });
  const retryEligibleSpecialists = () => {
    void eligibleSpecialistsQuery.refetch();
  };
  const retryRoutingOptions = () => {
    void routingOptionsQuery.refetch();
  };
  const specialistOptions: SpecialistOptions = !shouldLoadEligibleSpecialists
    ? { items: [], onRetry: retryEligibleSpecialists, status: "idle" }
    : eligibleSpecialistsQuery.isPending
      ? { items: [], onRetry: retryEligibleSpecialists, status: "loading" }
      : eligibleSpecialistsQuery.isError
        ? { items: [], onRetry: retryEligibleSpecialists, status: "error" }
        : {
            items: eligibleSpecialistsQuery.data.items,
            onRetry: retryEligibleSpecialists,
            status: "ready",
          };
  const routingOptions: RoutingOptions = !shouldLoadRoutingOptions
    ? { items: [], onRetry: retryRoutingOptions, status: "idle" }
    : routingOptionsQuery.isPending
      ? { items: [], onRetry: retryRoutingOptions, status: "loading" }
      : routingOptionsQuery.isError
        ? { items: [], onRetry: retryRoutingOptions, status: "error" }
        : {
            items: routingOptionsQuery.data.items,
            onRetry: retryRoutingOptions,
            route: routingOptionsQuery.data.route,
            status: "ready",
          };
  const detailState = detailQuery.isPending
    ? "loading"
    : detailQuery.isError
      ? "error"
      : "ready";

  if (!session) return null;
  if (listQuery.isPending) {
    return <PageState kind="loading" title="Loading work queue" />;
  }
  if (listQuery.isError) {
    return (
      <PageState
        action={
          <button className="button" onClick={() => void listQuery.refetch()}>
            Try again
          </button>
        }
        kind="error"
        title="Work queue could not be loaded"
      >
        Check your connection and try again.
      </PageState>
    );
  }

  const mutationError = claim.error ?? complete.error;
  const Container = embedded ? "section" : "main";
  const Heading = embedded ? "h2" : "h1";
  return (
    <Container className={embedded ? "page-stack workspace-work-queue" : "page-stack"}>
      <header className="page-heading">
        <div>
          <span>{eyebrow}</span>
          <Heading>{title}</Heading>
          <p>{description}</p>
        </div>
        <div className="queue-count">
          <ClipboardList aria-hidden="true" size={18} />
          <strong>{items.length}</strong>
          <span>waiting</span>
        </div>
      </header>
      {mutationError ? (
        <p className="form-banner form-banner--error" role="alert">
          {mutationError instanceof ApiError
            ? mutationError.message
            : "The work item could not be updated."}
        </p>
      ) : null}
      {items.length === 0 ? (
        <PageState
          action={requestId ? <Link className="button" to={roleRoutes[session.user.role]}>Open {queueLabelForRole(session.user.role)}</Link> : undefined}
          kind="empty"
          title={requestId ? "This action is no longer available" : "No items waiting"}
        >
          {requestId
            ? "It may have been completed, claimed by somebody else or removed from your authorised scope."
            : "New work will appear here when it reaches your team."}
        </PageState>
      ) : (
        <div className="queue-layout">
          <WorkQueueList
            currentUserId={session.user.id}
            hasMore={listQuery.hasNextPage}
            items={items}
            loadingMore={listQuery.isFetchingNextPage}
            onLoadMore={() => void listQuery.fetchNextPage()}
            onSelect={setSelectedId}
            selectedId={selected?.id}
          />
          <WorkQueueDetail
            canLoadDetail={canLoadDetail}
            detail={detailQuery.data}
            detailError={detailQuery.isError}
            detailLoading={detailQuery.isPending}
            detailState={detailState}
            disabled={claim.isPending || complete.isPending}
            item={selected}
            onActionChange={(action) => selected && setSelectedAction({ action, workItemId: selected.id })}
            onClaim={(item) => claim.mutate(item)}
            onComplete={(action, item) => complete.mutate({ action, item })}
            onRetryDetail={() => void detailQuery.refetch()}
            routingOptions={routingOptions}
            session={session}
            specialistOptions={specialistOptions}
          />
        </div>
      )}
    </Container>
  );
}
