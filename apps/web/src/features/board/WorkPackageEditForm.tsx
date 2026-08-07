import { useMutation } from "@tanstack/react-query";
import type { ChangeEvent, ReactNode } from "react";
import { useState } from "react";

import { boardApi } from "../../lib/api/boardClient";
import type {
  Iteration,
  WorkPackage,
  WorkPackagePriority,
} from "../../lib/api/boardTypes";
import { ApiError } from "../../lib/api/client";
import type { TeamMember, TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import type { Session } from "../../lib/api/types";

interface Props {
  access: TeamWorkspaceAccess;
  item: WorkPackage;
  items: WorkPackage[];
  iterations: Iteration[];
  members: TeamMember[];
  onUpdated: (item: WorkPackage) => void;
  session: Session;
}

export function WorkPackageEditForm({
  access,
  item,
  items,
  iterations,
  members,
  onUpdated,
  session,
}: Props) {
  const current = members.filter((member) => member.state === "CURRENT");
  const dependencies = items.filter((candidate) => candidate.id !== item.id);
  const [title, setTitle] = useState(item.title);
  const [description, setDescription] = useState(item.description);
  const [owner, setOwner] = useState(item.ownerUserId);
  const [contributors, setContributors] = useState(
    item.contributors.map((contributor) => contributor.userId),
  );
  const [points, setPoints] = useState(item.estimatePoints);
  const [minutes, setMinutes] = useState(item.remainingEffortMinutes);
  const [dueOn, setDueOn] = useState(item.dueOn);
  const [priority, setPriority] = useState<WorkPackagePriority>(item.priority);
  const [blockers, setBlockers] = useState(item.blockers);
  const [criteria, setCriteria] = useState(item.acceptanceCriteria);
  const [requestId, setRequestId] = useState(item.linkedRequestId ?? "");
  const [dependencyIds, setDependencyIds] = useState(item.dependencyIds);
  const [iterationId, setIterationId] = useState(item.iterationId ?? "");
  const mutation = useMutation({
    mutationFn: () =>
      boardApi.updatePackage(
        access.teamId,
        item.id,
        {
          grantId: access.grantId,
          title,
          description,
          ownerUserId: owner,
          contributorIds: contributors,
          estimatePoints: points,
          remainingEffortMinutes: minutes,
          dueOn,
          priority,
          blockers,
          acceptanceCriteria: criteria,
          linkedRequestId: requestId || null,
          dependencyIds,
          iterationId: iterationId || null,
          expectedVersion: item.version,
        },
        session.csrfToken,
      ),
    onSuccess: onUpdated,
  });
  return (
    <section className="package-edit-panel">
      <header>
        <span>Versioned planning change</span>
        <h2>Edit or hand over package</h2>
        <p>Managers can reassign ownership only to a current member of this team.</p>
      </header>
      <form onSubmit={(event) => { event.preventDefault(); mutation.mutate(); }}>
        <Field label="Edit title"><input maxLength={160} minLength={3} onChange={(event) => setTitle(event.target.value)} required value={title} /></Field>
        <Field label="Edit description"><textarea maxLength={4000} onChange={(event) => setDescription(event.target.value)} required value={description} /></Field>
        <div className="planning-form-grid">
          <Field label="Edit owner"><select onChange={(event) => setOwner(event.target.value)} required value={owner}>{current.map((member) => <option key={member.accountId} value={member.accountId}>{member.displayName}</option>)}</select></Field>
          <Field label="Edit contributors"><select multiple onChange={(event) => setContributors(selected(event))} required value={contributors}>{current.map((member) => <option key={member.accountId} value={member.accountId}>{member.displayName}</option>)}</select></Field>
        </div>
        <div className="planning-form-grid">
          <Field label="Edit estimate points"><input max={100} min={1} onChange={(event) => setPoints(Number(event.target.value))} required type="number" value={points} /></Field>
          <Field label="Edit remaining minutes"><input max={100000} min={0} onChange={(event) => setMinutes(Number(event.target.value))} required type="number" value={minutes} /></Field>
        </div>
        <div className="planning-form-grid">
          <Field label="Edit due date"><input onChange={(event) => setDueOn(event.target.value)} required type="date" value={dueOn} /></Field>
          <Field label="Edit priority"><select onChange={(event) => setPriority(event.target.value as WorkPackagePriority)} required value={priority}>{["LOW", "MEDIUM", "HIGH", "URGENT"].map((value) => <option key={value}>{value}</option>)}</select></Field>
        </div>
        <Field label="Edit blockers or none"><textarea maxLength={4000} onChange={(event) => setBlockers(event.target.value)} required value={blockers} /></Field>
        <Field label="Edit acceptance criteria"><textarea maxLength={4000} onChange={(event) => setCriteria(event.target.value)} required value={criteria} /></Field>
        <div className="planning-form-grid">
          <Optional label="Edit linked request ID"><input onChange={(event) => setRequestId(event.target.value)} placeholder="UUID" value={requestId} /></Optional>
          <Optional label="Edit iteration"><select onChange={(event) => setIterationId(event.target.value)} value={iterationId}><option value="">No iteration</option>{iterations.filter((iteration) => iteration.status !== "CLOSED" || iteration.id === iterationId).map((iteration) => <option key={iteration.id} value={iteration.id}>{iteration.name}</option>)}</select></Optional>
        </div>
        <Optional label="Edit dependencies"><select multiple onChange={(event) => setDependencyIds(selected(event))} value={dependencyIds}>{dependencies.map((dependency) => <option key={dependency.id} value={dependency.id}>{dependency.title}</option>)}</select></Optional>
        {mutation.isError ? <p role="alert">{message(mutation.error)}</p> : null}
        <button className="button button--primary" disabled={mutation.isPending} type="submit">Save package</button>
      </form>
    </section>
  );
}

function selected(event: ChangeEvent<HTMLSelectElement>) {
  return Array.from(event.target.selectedOptions, (option) => option.value);
}

function Field({ children, label }: { children: ReactNode; label: string }) {
  return <label className="form-field">{label}<span className="field-hint">Required</span>{children}</label>;
}

function Optional({ children, label }: { children: ReactNode; label: string }) {
  return <label className="form-field">{label}<span className="field-hint">Optional</span>{children}</label>;
}

function message(error: Error) {
  return error instanceof ApiError ? error.message : error.message || "The package change could not be saved.";
}
