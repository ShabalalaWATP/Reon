import { useMutation } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useState } from "react";

import { boardApi } from "../../lib/api/boardClient";
import type { Iteration, WorkPackage, WorkPackagePriority } from "../../lib/api/boardTypes";
import { ApiError } from "../../lib/api/client";
import type { TeamMember, TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import type { Session } from "../../lib/api/types";

export function WorkPackageForm({ access, iterations, members, onCreated, session }: {
  access: TeamWorkspaceAccess;
  iterations: Iteration[];
  members: TeamMember[];
  onCreated: (item: WorkPackage) => void;
  session: Session;
}) {
  const current = members.filter((item) => item.state === "CURRENT");
  const analysts = current.filter((item) => item.role === "DELIVERY_SPECIALIST");
  const isManager = Boolean(access.grantId && access.permissions.includes("BOARD"));
  const initialOwner = isManager ? "" : session.user.id;
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [owner, setOwner] = useState(initialOwner);
  const [contributor, setContributor] = useState("");
  const [points, setPoints] = useState(3);
  const [minutes, setMinutes] = useState(120);
  const [dueOn, setDueOn] = useState("");
  const [priority, setPriority] = useState<WorkPackagePriority>("MEDIUM");
  const [blockers, setBlockers] = useState("");
  const [criteria, setCriteria] = useState("");
  const [requestId, setRequestId] = useState("");
  const [iterationId, setIterationId] = useState("");
  const mutation = useMutation({
    mutationFn: () => {
      return boardApi.createPackage(access.teamId, {
        grantId: access.grantId,
        title,
        description,
        ownerUserId: owner,
        contributorIds: [contributor],
        estimatePoints: points,
        remainingEffortMinutes: minutes,
        dueOn,
        priority,
        blockers,
        acceptanceCriteria: criteria,
        linkedRequestId: requestId || null,
        dependencyIds: [],
        iterationId: iterationId || null,
      }, session.csrfToken);
    },
    onSuccess: (item) => {
      setTitle(""); setDescription(""); setContributor(""); setBlockers(""); setCriteria(""); setRequestId("");
      onCreated(item);
    },
  });
  return (
    <section className="package-form-panel">
      <header><span>Independent planning record</span><h2>Create work package</h2><p>Required delivery detail is stored separately from the authoritative Camunda request state.</p></header>
      <form onSubmit={(event) => { event.preventDefault(); mutation.mutate(); }}>
        <Field label="Title"><input maxLength={160} minLength={3} onChange={(event) => setTitle(event.target.value)} required value={title} /></Field>
        <Field label="Description"><textarea maxLength={4000} onChange={(event) => setDescription(event.target.value)} required rows={4} value={description} /></Field>
        <div className="planning-form-grid">
          <Field label="Owner"><select disabled={!isManager} onChange={(event) => setOwner(event.target.value)} required value={owner}><option value="">Select an owner</option>{current.map((item) => <option key={item.accountId} value={item.accountId}>{item.displayName}</option>)}</select></Field>
          <Field label="Contributor"><select onChange={(event) => setContributor(event.target.value)} required value={contributor}><option value="">Select a contributor</option>{analysts.map((item) => <option key={item.accountId} value={item.accountId}>{item.displayName}</option>)}</select></Field>
        </div>
        <div className="planning-form-grid">
          <Field label="Estimate points"><input max={100} min={1} onChange={(event) => setPoints(Number(event.target.value))} required type="number" value={points} /></Field>
          <Field label="Remaining effort (minutes)"><input max={100000} min={0} onChange={(event) => setMinutes(Number(event.target.value))} required type="number" value={minutes} /></Field>
        </div>
        <div className="planning-form-grid">
          <Field label="Due date"><input onChange={(event) => setDueOn(event.target.value)} required type="date" value={dueOn} /></Field>
          <Field label="Priority"><select onChange={(event) => setPriority(event.target.value as WorkPackagePriority)} required value={priority}>{["LOW", "MEDIUM", "HIGH", "URGENT"].map((item) => <option key={item}>{item}</option>)}</select></Field>
        </div>
        <Field label="Blockers or none"><textarea maxLength={4000} onChange={(event) => setBlockers(event.target.value)} required rows={3} value={blockers} /></Field>
        <Field label="Acceptance criteria"><textarea maxLength={4000} onChange={(event) => setCriteria(event.target.value)} required rows={3} value={criteria} /></Field>
        <div className="planning-form-grid">
          <label className="form-field">Linked request ID<span className="field-hint">Optional</span><input onChange={(event) => setRequestId(event.target.value)} placeholder="UUID" value={requestId} /></label>
          <label className="form-field">Iteration<span className="field-hint">Optional</span><select onChange={(event) => setIterationId(event.target.value)} value={iterationId}><option value="">No iteration</option>{iterations.filter((item) => item.status !== "CLOSED").map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        </div>
        {mutation.isError ? <p role="alert">{errorMessage(mutation.error)}</p> : null}
        <button className="button button--primary" disabled={mutation.isPending} type="submit">{mutation.isPending ? "Creating…" : "Create package"}</button>
      </form>
    </section>
  );
}

function Field({ children, label }: { children: ReactNode; label: string }) {
  return <label className="form-field">{label}<span className="field-hint">Required</span>{children}</label>;
}

function errorMessage(error: Error) {
  return error instanceof ApiError ? error.message : error.message || "The work package could not be created.";
}
