import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router";

import { ModalDrawer } from "../../components/ModalDrawer";
import { PageState } from "../../components/PageState";
import { api } from "../../lib/api/client";
import type {
  BoardColumn,
  BoardItem,
  WorkPackage,
} from "../../lib/api/boardTypes";
import type { PlanningCockpit } from "../../lib/api/planningEvolutionTypes";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import { boardLabel, daysInState, dueSignal } from "./boardPresentation";

export function WorkItemInspector({
  item,
  moving,
  packages,
  planning,
  teamId,
  userId,
  onClose,
  onMove,
}: {
  item: BoardItem | null;
  moving: boolean;
  packages: WorkPackage[];
  planning?: PlanningCockpit;
  teamId: string;
  userId: string;
  onClose: () => void;
  onMove: (item: BoardItem, target: BoardColumn, reason: string) => void;
}) {
  const request = useQuery({
    queryKey: protectedQueryKeys.request(userId, item?.linkedRequestId ?? undefined),
    queryFn: () => api.request(item!.linkedRequestId!),
    enabled: Boolean(item?.itemType === "SERVICE_REQUEST" && item.linkedRequestId),
  });
  const packageItem = item?.itemType === "WORK_PACKAGE"
    ? packages.find((value) => value.id === item.id)
    : undefined;
  return (
    <ModalDrawer label="Work item details" onClose={onClose} open={Boolean(item)}>
      {item ? (
        <div className="work-inspector">
          <header className="work-inspector__heading">
            <span>{item.itemType === "SERVICE_REQUEST" ? "Service request" : "Work package"} · {item.reference}</span>
            <h2>{item.title}</h2>
            <p>Inspect the complete authorised context before taking an explicit action.</p>
          </header>
          <WorkSummary item={item} />
          {item.itemType === "SERVICE_REQUEST" ? (
            request.isPending ? <PageState kind="loading" title="Loading request context" />
              : request.isError ? <PageState action={<button className="button" onClick={() => void request.refetch()}>Try again</button>} kind="error" title="Request context is unavailable" />
                : request.data ? <RequestContext value={request.data} /> : null
          ) : packageItem ? <PackageContext packages={packages} planning={planning} value={packageItem} />
            : <PageState kind="empty" title="Package detail is not on this page">Open Planning to inspect the full package register.</PageState>}
          <InspectorActions item={item} moving={moving} onMove={onMove} teamId={teamId} />
        </div>
      ) : null}
    </ModalDrawer>
  );
}

function WorkSummary({ item }: { item: BoardItem }) {
  const due = dueSignal(item.dueOn);
  return (
    <dl className="work-inspector__summary">
      <div><dt>Status</dt><dd>{boardLabel(item.column)}</dd></div>
      <div><dt>Priority</dt><dd>{boardLabel(item.priority)}</dd></div>
      <div><dt>Owner</dt><dd>{item.ownerDisplayName ?? "Unassigned"}</dd></div>
      <div><dt>Due</dt><dd><span className={`status-signal status-signal--${due.tone}`}>{due.label}</span>{item.dueOn}</dd></div>
      <div><dt>State age</dt><dd>{daysInState(item.changedAt)}</dd></div>
    </dl>
  );
}

function RequestContext({ value }: { value: Awaited<ReturnType<typeof api.request>> }) {
  const openClarifications = value.clarifications.filter((item) => item.status === "OPEN");
  return (
    <div className="work-inspector__sections">
      {value.status === "CUSTOMER_INFORMATION_REQUIRED" ? <section className="inspector-attention"><h3>Waiting for customer information</h3><p>{openClarifications.length} clarification request{openClarifications.length === 1 ? " is" : "s are"} currently open.</p></section> : null}
      <section><h3>Customer requirement</h3><dl><div><dt>Customer</dt><dd>{value.requester.displayName}</dd></div><div><dt>Question</dt><dd>{value.questionToAnswer}</dd></div><div><dt>Outcome</dt><dd>{value.desiredOutcome}</dd></div><div><dt>Success</dt><dd>{value.successCriteria}</dd></div></dl></section>
      <section><h3>Delivery context</h3><dl><div><dt>Team</dt><dd>{value.assignedDeliveryTeam ?? "Routing in progress"}</dd></div><div><dt>Lead</dt><dd>{value.assignedSpecialist?.displayName ?? "Unassigned"}</dd></div><div><dt>Contributors</dt><dd>{value.contributors.map((item) => item.displayName).join(", ") || "None"}</dd></div><div><dt>Preferred product</dt><dd>{value.preferredDeliverableType}</dd></div></dl></section>
      {openClarifications.map((thread) => <section key={thread.id}><h3>Clarification {thread.sequence}</h3><p>{thread.question}</p><small>Response requested by {new Date(thread.responseDeadline).toLocaleString("en-GB")}</small></section>)}
    </div>
  );
}

function PackageContext({ packages, planning, value }: { packages: WorkPackage[]; planning?: PlanningCockpit; value: WorkPackage }) {
  const checklist = planning?.checklists.find((item) => item.packageId === value.id);
  const warnings = planning?.dependencies.filter((item) => item.packageId === value.id) ?? [];
  const activeReservations = value.reservations.filter((item) => item.status === "ACTIVE");
  return (
    <div className="work-inspector__sections">
      <section><h3>Package detail</h3><p>{value.description}</p><dl><div><dt>Estimate</dt><dd>{value.estimatePoints} points</dd></div><div><dt>Remaining</dt><dd>{value.remainingEffortMinutes} minutes</dd></div><div><dt>Contributors</dt><dd>{value.contributors.map((item) => item.displayName).join(", ") || "None"}</dd></div><div><dt>Iteration</dt><dd>{value.iterationId ?? "Not assigned"}</dd></div></dl></section>
      <section><h3>Acceptance and blockers</h3><p><strong>Acceptance:</strong> {value.acceptanceCriteria}</p><p><strong>Blockers:</strong> {value.blockers}</p></section>
      <section><h3>Dependencies</h3>{value.dependencyIds.length ? <ul>{value.dependencyIds.map((id) => <li key={id}>{packages.find((item) => item.id === id)?.title ?? id}</li>)}</ul> : <p>No dependencies recorded.</p>}{warnings.map((warning) => <p className="inspector-warning" key={`${warning.packageId}-${warning.dependencyReference}`}>{warning.dependencyReference}: {warning.warning}</p>)}</section>
      <section><h3>Checklist</h3>{checklist ? <><p>{checklist.completedCount} of {checklist.totalCount} complete from {checklist.templateName}.</p><ul className="inspector-checklist">{checklist.items.map((item) => <li key={item.id}><span aria-hidden="true">{item.completed ? "✓" : "○"}</span>{item.label}</li>)}</ul></> : <p>No checklist is attached.</p>}</section>
      <section><h3>Reserved capacity</h3>{activeReservations.length ? <ul>{activeReservations.map((item) => <li key={item.id}>{item.userDisplayName}: {item.minutes} minutes, {new Date(item.startsAt).toLocaleString("en-GB")}</li>)}</ul> : <p>No active reservations.</p>}</section>
      <section><h3>Recent package activity</h3>{value.activities.length ? <ol>{value.activities.slice(0, 8).map((activity) => <li key={activity.id}>{activity.summary} · {activity.actorDisplayName}</li>)}</ol> : <p>No activity recorded.</p>}</section>
    </div>
  );
}

function InspectorActions({ item, moving, onMove, teamId }: { item: BoardItem; moving: boolean; onMove: (item: BoardItem, target: BoardColumn, reason: string) => void; teamId: string }) {
  const [target, setTarget] = useState<BoardColumn | "">("");
  const [reason, setReason] = useState("");
  useEffect(() => { setTarget(""); setReason(""); }, [item.id]);
  return (
    <footer className="work-inspector__actions">
      {item.linkedRequestId ? <Link className="button button--primary" to={`/requests/${item.linkedRequestId}`}>Open full request</Link> : null}
      {item.itemType === "WORK_PACKAGE" ? <Link className="button button--quiet" to={`/teams/${teamId}/planning`}>Open in Planning</Link> : null}
      {item.availableColumns.length ? <form onSubmit={(event) => { event.preventDefault(); if (target) onMove(item, target, reason); }}>
        <label className="form-field">Move package to<span className="field-hint">Required</span><select onChange={(event) => setTarget(event.target.value as BoardColumn)} required value={target}><option value="">Select status</option>{item.availableColumns.map((column) => <option key={column} value={column}>{boardLabel(column)}</option>)}</select></label>
        <label className="form-field">Reason<span className="field-hint">Required</span><textarea maxLength={500} minLength={10} onChange={(event) => setReason(event.target.value)} required value={reason} /></label>
        <button className="button" disabled={moving || !target || reason.length < 10} type="submit">{moving ? "Moving…" : "Move package"}</button>
      </form> : item.itemType === "SERVICE_REQUEST" ? <p>Use the named workflow action on the request to change its stage.</p> : null}
    </footer>
  );
}
