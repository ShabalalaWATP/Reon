import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardList } from "lucide-react";
import { useState } from "react";

import { PageState } from "../../components/PageState";
import { StatusPill } from "../../components/StatusPill";
import { api, ApiError } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { ListResponse, WorkAction, WorkItem } from "../../lib/api/types";
import { useAuth } from "../../lib/auth/AuthProvider";
import { formatDate, statusLabels } from "../../lib/status";
import { RequestOverview } from "../requests/RequestOverview";
import type { SpecialistOptions } from "./EligibleSpecialistField";
import type { RoutingOptions } from "./RoutingDestinationField";
import { RelatedRecordPanel } from "./RelatedRecordPanel";
import { StaffDeliverableSection } from "./StaffDeliverableSection";
import { WorkActionPanel } from "./WorkActionPanel";
import {
  actionRequiresDestination,
  type WorkActionName,
} from "./workActionModel";

type StaffQueuePageProps = {
  description: string;
  eyebrow: string;
  title: string;
};

export function StaffQueuePage({
  description,
  eyebrow,
  title,
}: StaffQueuePageProps) {
  const { session } = useAuth();
  const userId = session?.user.id ?? "anonymous";
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedAction, setSelectedAction] = useState<{
    action: WorkActionName;
    workItemId: string;
  } | null>(null);
  const listQuery = useQuery({
    queryKey: protectedQueryKeys.workItems(userId),
    queryFn: api.workItems,
    enabled: Boolean(session),
    refetchInterval: 30_000,
  });
  const items = listQuery.data?.items ?? [];
  const selected = items.find((item) => item.id === selectedId) ?? items[0];
  const activeAction =
    selected &&
    selectedAction?.workItemId === selected.id &&
    selected.availableActions.includes(selectedAction.action)
      ? selectedAction.action
      : selected?.availableActions[0];
  const shouldLoadEligibleSpecialists = Boolean(
    selected &&
    session &&
    selected.stage === "DELIVERY_PLANNING" &&
    selected.assigneeId === session.user.id &&
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
    selected.assigneeId === session.user.id &&
    actionRequiresDestination(activeAction),
  );
  const canLoadDetail = Boolean(
    selected && session && selected.assigneeId === session.user.id,
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
      queryClient.setQueryData<ListResponse<WorkItem>>(
        protectedQueryKeys.workItems(userId),
        (current) => ({
          // Completion is only available after this queue has loaded, so the
          // cached list is an invariant at this point in the interaction.
          items: current!.items.filter((item) => item.id !== variables.item.id),
        }),
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
  return (
    <main className="page-stack">
      <header className="page-heading">
        <div>
          <span>{eyebrow}</span>
          <h1>{title}</h1>
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
        <PageState kind="empty" title="No items waiting">
          New work will appear here when it reaches your team.
        </PageState>
      ) : (
        <div className="queue-layout">
          <aside className="queue-list" aria-label="Work items">
            {items.map((item) => (
              <QueueRow
                currentUserId={session.user.id}
                item={item}
                key={item.id}
                onSelect={() => setSelectedId(item.id)}
                selected={item.id === selected?.id}
              />
            ))}
          </aside>
          <section className="queue-detail" aria-live="polite">
            {selected ? (
              <>
                <header className="queue-detail__heading">
                  <div>
                    <span className="mono-ref">{selected.requestReference}</span>
                    <h2>{selected.title}</h2>
                    <p>
                      {statusLabels[selected.stage]} · updated{" "}
                      {formatDate(selected.updatedAt, true)}
                    </p>
                  </div>
                  <StatusPill status={selected.stage} />
                </header>
                <div className="queue-detail__content">
                  {!selected.assigneeId ? (
                    <PageState kind="empty" title="Claim to view request context">
                      Request details remain protected until you take ownership.
                    </PageState>
                  ) : selected.assigneeId !== session.user.id ? (
                    <PageState kind="empty" title="Request context restricted">
                      Only the current owner can view this request.
                    </PageState>
                  ) : detailQuery.isPending ? (
                    <PageState kind="loading" title="Loading request context" />
                  ) : detailQuery.isError ? (
                    <PageState
                      action={
                        <button
                          className="button"
                          onClick={() => void detailQuery.refetch()}
                        >
                          Try again
                        </button>
                      }
                      kind="error"
                      title="Request context could not be loaded"
                    />
                  ) : (
                    <RequestOverview request={detailQuery.data} />
                  )}
                  <div className="queue-detail__decision">
                    {canLoadDetail && selected.stage === "TRIAGE_REVIEW" ? (
                      <RelatedRecordPanel
                        csrfToken={session.csrfToken}
                        userId={session.user.id}
                        workItemId={selected.id}
                      />
                    ) : null}
                    {canLoadDetail ? (
                      <StaffDeliverableSection
                        deliverable={detailQuery.data?.deliverable}
                        stage={selected.stage}
                        state={detailState}
                      />
                    ) : null}
                    {!canLoadDetail || detailQuery.data ? (
                      <WorkActionPanel
                        currentUserId={session.user.id}
                        disabled={claim.isPending || complete.isPending}
                        item={selected}
                        onActionChange={(action) =>
                          setSelectedAction({
                            action,
                            workItemId: selected.id,
                          })
                        }
                        onClaim={() => claim.mutate(selected)}
                        onComplete={(action) =>
                          complete.mutate({ action, item: selected })
                        }
                        routingOptions={routingOptions}
                        specialistOptions={specialistOptions}
                      />
                    ) : null}
                  </div>
                </div>
              </>
            ) : null}
          </section>
        </div>
      )}
    </main>
  );
}

function QueueRow({
  currentUserId,
  item,
  onSelect,
  selected,
}: {
  currentUserId: string;
  item: WorkItem;
  onSelect: () => void;
  selected: boolean;
}) {
  const ownership = !item.assigneeId
    ? "Available"
    : item.assigneeId === currentUserId
      ? "Assigned to you"
      : `Assigned to ${item.assigneeDisplayName ?? "team member"}`;
  return (
    <button
      aria-current={selected ? "true" : undefined}
      className={`queue-row${selected ? " queue-row--selected" : ""}`}
      onClick={onSelect}
      type="button"
    >
      <span className="queue-row__indicator" aria-hidden="true" />
      <span className="mono-ref">{item.requestReference}</span>
      <strong>{item.title}</strong>
      <small>{statusLabels[item.stage]}</small>
      <span>{ownership}</span>
      <time dateTime={item.updatedAt}>{formatDate(item.updatedAt)}</time>
    </button>
  );
}
