import { StatusPill } from "../../components/StatusPill";
import { PageState } from "../../components/PageState";
import { useState } from "react";
import type { RequestDetail, Session, WorkAction, WorkItem } from "../../lib/api/types";
import { elapsedTime } from "../../lib/serviceTiming";
import { formatDate, statusLabels } from "../../lib/status";
import { StaffProductAction } from "../products/StaffProductAction";
import { RequestOverview } from "../requests/RequestOverview";
import { RequestConversations } from "../requests/RequestConversations";
import type { SpecialistOptions } from "./EligibleSpecialistField";
import { RelatedRecordPanel } from "./RelatedRecordPanel";
import type { RoutingOptions } from "./RoutingDestinationField";
import { StaffDeliverableSection } from "./StaffDeliverableSection";
import { WorkActionPanel } from "./WorkActionPanel";
import type { WorkActionName } from "./workActionModel";

type Props = {
  canLoadDetail: boolean;
  detail?: RequestDetail;
  detailError: boolean;
  detailLoading: boolean;
  detailState: "loading" | "error" | "ready";
  disabled: boolean;
  item?: WorkItem;
  onActionChange: (action: WorkActionName) => void;
  onClaim: (item: WorkItem) => void;
  onComplete: (action: WorkAction, item: WorkItem) => void;
  onRetryDetail: () => void;
  routingOptions: RoutingOptions;
  session: Session;
  specialistOptions: SpecialistOptions;
};

export function WorkQueueDetail({
  canLoadDetail,
  detail,
  detailError,
  detailLoading,
  detailState,
  disabled,
  item,
  onActionChange,
  onClaim,
  onComplete,
  onRetryDetail,
  routingOptions,
  session,
  specialistOptions,
}: Props) {
  return (
    <section className="queue-detail" aria-live="polite">
      {item ? (
        <>
          <header className="queue-detail__heading">
            <div>
              <span className="mono-ref">{item.requestReference}</span>
              <h2>{item.title}</h2>
              <p>
                {statusLabels[item.stage]} · updated {formatDate(item.updatedAt, true)} · waiting in
                this task for {elapsedTime(item.createdAt)}
              </p>
            </div>
            <StatusPill status={item.stage} />
          </header>
          <div className="queue-detail__content">
            <div className="queue-detail__decision">
              {/* A review decision must follow the work it judges, so the
                  submitted product leads at review stages. At routing stages
                  there is no product yet and the decision leads directly. */}
              {canLoadDetail ? (
                <StaffDeliverableSection
                  deliverable={detail?.deliverable}
                  stage={item.stage}
                  state={detailState}
                />
              ) : null}
              {!canLoadDetail || detail ? (
                <WorkActionPanel
                  claimAllowed={session.user.role !== "DELIVERY_SPECIALIST"}
                  currentUserId={session.user.id}
                  disabled={disabled}
                  item={item}
                  managedProducts={detail?.productMode === "MANAGED"}
                  onActionChange={onActionChange}
                  onClaim={() => onClaim(item)}
                  onComplete={(action) => onComplete(action, item)}
                  routingOptions={routingOptions}
                  specialistOptions={specialistOptions}
                />
              ) : null}
              {canLoadDetail ? (
                <StaffProductAction
                  requestId={item.requestId}
                  requestVersion={item.requestVersion}
                  stage={item.stage}
                />
              ) : null}
              {detail && item.stage === "TRIAGE_REVIEW" ? (
                <RelatedRecordPanel session={session} workItemId={item.id} />
              ) : null}
            </div>
            <RequestContext
              detail={detail}
              error={detailError}
              item={item}
              loading={detailLoading}
              onRetry={onRetryDetail}
              session={session}
            />
            {detail ? (
              <RequestCorrespondence
                key={item.requestId}
                requestId={item.requestId}
                status={detail.status}
              />
            ) : null}
          </div>
        </>
      ) : null}
    </section>
  );
}

function RequestCorrespondence({
  requestId,
  status,
}: {
  requestId: string;
  status: RequestDetail["status"];
}) {
  const [open, setOpen] = useState(false);
  return (
    <details
      className="queue-detail__correspondence"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        <span>Recorded correspondence</span>
        <strong>Request information from the Customer or another team</strong>
      </summary>
      {open ? <RequestConversations requestId={requestId} status={status} /> : null}
    </details>
  );
}

function RequestContext({
  detail,
  error,
  item,
  loading,
  onRetry,
  session,
}: {
  detail?: RequestDetail;
  error: boolean;
  item: WorkItem;
  loading: boolean;
  onRetry: () => void;
  session: Session;
}) {
  const assignedToCurrentUser = item.assignedToCurrentUser || item.assigneeId === session.user.id;
  if (assignedToCurrentUser) {
    if (loading) return <PageState kind="loading" title="Loading request context" />;
    if (error) {
      return (
        <PageState
          action={
            <button className="button" onClick={onRetry}>
              Try again
            </button>
          }
          kind="error"
          title="Request context could not be loaded"
        />
      );
    }
    return detail ? <RequestOverview request={detail} /> : null;
  }
  if (!item.assigneeId) {
    return session.user.role === "DELIVERY_SPECIALIST" ? (
      <PageState kind="empty" title="Manager assignment required">
        This request must be assigned to you by a Team Manager.
      </PageState>
    ) : (
      <PageState kind="empty" title="Claim to view request context">
        Request details remain protected until you take ownership.
      </PageState>
    );
  }
  if (item.assigneeId !== session.user.id) {
    return (
      <PageState kind="empty" title="Request context restricted">
        Only the current owner can view this request.
      </PageState>
    );
  }
  return null;
}
