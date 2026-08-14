import { ClipboardList } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router";

import { PageState } from "../../components/PageState";
import { ApiError } from "../../lib/api/client";
import type { Session } from "../../lib/api/types";
import { queueLabelForRole, roleRoutes } from "../../lib/routes";
import { WorkQueueDetail } from "./WorkQueueDetail";
import { WorkQueueList } from "./WorkQueueList";
import { useStaffQueueController } from "./useStaffQueueController";
import "../../styles/work.css";
import "../../styles/work-actions.css";

type StaffQueuePageProps = {
  afterQueue?: (actionRequestIds: ReadonlySet<string>) => ReactNode;
  description: string;
  embedded?: boolean;
  eyebrow: string;
  teamId?: string;
  title: string;
};

export function StaffQueuePage(props: StaffQueuePageProps) {
  const queue = useStaffQueueController(props.teamId);
  if (!queue.session) return null;
  if (queue.listQuery.isPending) return <PageState kind="loading" title="Loading work queue" />;
  if (queue.listQuery.isError) {
    return (
      <PageState
        action={
          <button className="button" onClick={() => void queue.listQuery.refetch()}>
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
  return <ReadyQueue props={props} queue={queue} session={queue.session} />;
}

function ReadyQueue({
  props,
  queue,
  session,
}: {
  props: StaffQueuePageProps;
  queue: ReturnType<typeof useStaffQueueController>;
  session: Session;
}) {
  const Container = props.embedded ? "section" : "main";
  const Heading = props.embedded ? "h2" : "h1";
  return (
    <Container className={props.embedded ? "page-stack workspace-work-queue" : "page-stack"}>
      <header className="page-heading">
        <div>
          <span>{props.eyebrow}</span>
          <Heading>{props.title}</Heading>
          <p>{props.description}</p>
        </div>
        <div className="queue-count">
          <ClipboardList aria-hidden="true" size={18} />
          <strong>{queue.items.length}</strong>
          <span>waiting</span>
        </div>
      </header>
      <MutationError error={queue.mutationError} />
      {queue.items.length === 0 ? (
        <EmptyQueue requestId={queue.requestId} role={session.user.role} />
      ) : (
        <div className="queue-layout">
          <WorkQueueList
            currentUserId={session.user.id}
            hasMore={queue.listQuery.hasNextPage}
            items={queue.items}
            loadingMore={queue.listQuery.isFetchingNextPage}
            onLoadMore={() => void queue.listQuery.fetchNextPage()}
            onSelect={queue.selectItem}
            selectedId={queue.selected?.id}
            splitQualityStages={session.user.role === "QUALITY_RELEASE"}
          />
          <WorkQueueDetail
            canLoadDetail={queue.canLoadDetail}
            detail={queue.detail.data}
            detailError={queue.detail.isError}
            detailLoading={queue.detail.isPending}
            detailState={
              queue.detail.isPending ? "loading" : queue.detail.isError ? "error" : "ready"
            }
            disabled={queue.claim.isPending || queue.complete.isPending}
            item={queue.selected}
            onActionChange={(action) =>
              queue.selected && queue.selectAction({ action, workItemId: queue.selected.id })
            }
            onClaim={queue.claim.mutate}
            onComplete={(action, item) => queue.complete.mutate({ action, item })}
            onRetryDetail={() => void queue.detail.refetch()}
            routingOptions={queue.routingOptions}
            session={session}
            specialistOptions={queue.specialistOptions}
          />
        </div>
      )}
      {props.afterQueue?.(new Set(queue.items.map((item) => item.requestId)))}
    </Container>
  );
}

function MutationError({ error }: { error: Error | null }) {
  if (!error) return null;
  return (
    <p className="form-banner form-banner--error" role="alert">
      {error instanceof ApiError ? error.message : "The work item could not be updated."}
    </p>
  );
}

function EmptyQueue({
  requestId,
  role,
}: {
  requestId?: string;
  role: Parameters<typeof queueLabelForRole>[0];
}) {
  return (
    <PageState
      action={
        requestId ? (
          <Link className="button" to={roleRoutes[role]}>
            Open {queueLabelForRole(role)}
          </Link>
        ) : undefined
      }
      kind="empty"
      title={requestId ? "This action is no longer available" : "No items waiting"}
    >
      {requestId
        ? "It may have been completed, claimed by somebody else or removed from your authorised scope."
        : "New work will appear here when it reaches your team."}
    </PageState>
  );
}
