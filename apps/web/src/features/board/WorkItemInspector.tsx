import { type UseQueryResult, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router";

import { ModalDrawer } from "../../components/ModalDrawer";
import { PageState } from "../../components/PageState";
import { api } from "../../lib/api/client";
import type { BoardColumn, BoardItem, WorkPackage } from "../../lib/api/boardTypes";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import type { RequestDetail, Session } from "../../lib/api/types";
import { boardLabel, daysInState, dueSignal } from "./boardPresentation";
import { TaskHastenerPanel } from "./TaskHastenerPanel";
import { PackageContext, RequestContext } from "./WorkItemContext";

export function WorkItemInspector({
  access,
  item,
  moving,
  packages,
  session,
  onClose,
  onMove,
}: {
  access: TeamWorkspaceAccess;
  item: BoardItem | null;
  moving: boolean;
  packages: WorkPackage[];
  userId: string;
  session: Session;
  onClose: () => void;
  onMove: (item: BoardItem, target: BoardColumn, reason: string) => void;
}) {
  const queryKeys = protectedQueryKeys(session);
  const request = useQuery({
    queryKey: queryKeys.request(item?.linkedRequestId ?? undefined),
    queryFn: () => api.request(item!.linkedRequestId!),
    enabled: Boolean(item?.itemType === "SERVICE_REQUEST" && item.linkedRequestId),
  });
  const packageItem =
    item?.itemType === "WORK_PACKAGE" ? packages.find((value) => value.id === item.id) : undefined;
  return (
    <ModalDrawer label="Work item details" onClose={onClose} open={Boolean(item)}>
      {item ? (
        <div className="work-inspector">
          <header className="work-inspector__heading">
            <span>
              {item.itemType === "SERVICE_REQUEST" ? "Service request" : "Work package"} ·{" "}
              {item.reference}
            </span>
            <h2>{item.title}</h2>
            <p>Inspect the complete authorised context before taking an explicit action.</p>
          </header>
          <WorkSummary item={item} />
          <InspectorContext
            access={access}
            item={item}
            packageItem={packageItem}
            packages={packages}
            request={request}
            session={session}
          />
          <InspectorActions item={item} moving={moving} onMove={onMove} />
        </div>
      ) : null}
    </ModalDrawer>
  );
}

function InspectorContext({
  access,
  item,
  packageItem,
  packages,
  request,
  session,
}: {
  access: TeamWorkspaceAccess;
  item: BoardItem;
  packageItem: WorkPackage | undefined;
  packages: WorkPackage[];
  request: UseQueryResult<RequestDetail, Error>;
  session: Session;
}) {
  if (item.itemType !== "SERVICE_REQUEST") {
    return packageItem ? (
      <PackageContext packages={packages} value={packageItem} />
    ) : (
      <PageState kind="empty" title="Package detail is not on this page">
        Refresh the board to load the current package detail.
      </PageState>
    );
  }
  if (request.isPending) return <PageState kind="loading" title="Loading request context" />;
  if (request.isError) {
    return (
      <PageState
        action={
          <button className="button" onClick={() => void request.refetch()}>
            Try again
          </button>
        }
        kind="error"
        title="Request context is unavailable"
      />
    );
  }
  if (!request.data) return null;
  return (
    <>
      <RequestContext value={request.data} />
      <TaskHastenerPanel access={access} request={request.data} session={session} />
    </>
  );
}

function WorkSummary({ item }: { item: BoardItem }) {
  const due = dueSignal(item.dueOn);
  return (
    <dl className="work-inspector__summary">
      <div>
        <dt>Status</dt>
        <dd>{boardLabel(item.column)}</dd>
      </div>
      <div>
        <dt>Priority</dt>
        <dd>{boardLabel(item.priority)}</dd>
      </div>
      <div>
        <dt>Owner</dt>
        <dd>{item.ownerDisplayName ?? "Unassigned"}</dd>
      </div>
      <div>
        <dt>Due</dt>
        <dd>
          <span className={`status-signal status-signal--${due.tone}`}>{due.label}</span>
          {item.dueOn}
        </dd>
      </div>
      <div>
        <dt>State age</dt>
        <dd>{daysInState(item.changedAt)}</dd>
      </div>
    </dl>
  );
}

function InspectorActions({
  item,
  moving,
  onMove,
}: {
  item: BoardItem;
  moving: boolean;
  onMove: (item: BoardItem, target: BoardColumn, reason: string) => void;
}) {
  const [target, setTarget] = useState<BoardColumn | "">("");
  const [reason, setReason] = useState("");
  useEffect(() => {
    setTarget("");
    setReason("");
  }, [item.id]);
  return (
    <footer className="work-inspector__actions">
      {item.linkedRequestId ? (
        <Link className="button button--primary" to={`/requests/${item.linkedRequestId}`}>
          Open full request
        </Link>
      ) : null}
      {item.availableColumns.length ? (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (target) onMove(item, target, reason);
          }}
        >
          <label className="form-field">
            Move package to<span className="field-hint">Required</span>
            <select
              onChange={(event) => setTarget(event.target.value as BoardColumn)}
              required
              value={target}
            >
              <option value="">Select status</option>
              {item.availableColumns.map((column) => (
                <option key={column} value={column}>
                  {boardLabel(column)}
                </option>
              ))}
            </select>
          </label>
          <label className="form-field">
            Reason<span className="field-hint">Required</span>
            <textarea
              maxLength={500}
              minLength={10}
              onChange={(event) => setReason(event.target.value)}
              required
              value={reason}
            />
          </label>
          <button
            className="button"
            disabled={moving || !target || reason.length < 10}
            type="submit"
          >
            {moving ? "Moving…" : "Move package"}
          </button>
        </form>
      ) : item.itemType === "SERVICE_REQUEST" ? (
        <p>Use the named workflow action on the request to change its stage.</p>
      ) : null}
    </footer>
  );
}
