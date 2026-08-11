import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useState } from "react";
import { Link } from "react-router";

import { PageState } from "../../components/PageState";
import { boardApi } from "../../lib/api/boardClient";
import type { Iteration, WorkPackage } from "../../lib/api/boardTypes";
import { ApiError, api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import type { Session } from "../../lib/api/types";
import { useAuth } from "../../lib/auth/AuthProvider";
import { localDateTimeInputValue } from "../../lib/dateInputs";
import { boardLabel } from "./boardPresentation";
import { WorkPackageEditForm } from "./WorkPackageEditForm";
import { PlanningEnhancements } from "./PlanningEnhancements";

export function TeamPlanningPage({ access }: { access: TeamWorkspaceAccess }) {
  const { session } = useAuth();
  if (!session) return <PageState kind="error" title="Sign in is required" />;
  return <AuthenticatedTeamPlanning access={access} session={session} />;
}

function AuthenticatedTeamPlanning({ access, session }: { access: TeamWorkspaceAccess; session: Session }) {
  const userId = session.user.id;
  const client = useQueryClient();
  const packages = useQuery({ queryKey: protectedQueryKeys.teamPackages(userId, access.teamId), queryFn: () => boardApi.packages(access.teamId) });
  const iterations = useQuery({ queryKey: protectedQueryKeys.teamIterations(userId, access.teamId), queryFn: () => boardApi.iterations(access.teamId) });
  const people = useQuery({ queryKey: protectedQueryKeys.teamPeople(userId, access.teamId), queryFn: () => api.teamPeople(access.teamId) });
  const [selectedId, setSelectedId] = useState("");
  const selected = packages.data?.items.find((item) => item.id === selectedId) ?? packages.data?.items[0];
  const refresh = () => Promise.all([
    client.invalidateQueries({ queryKey: protectedQueryKeys.teamPackages(userId, access.teamId) }),
    client.invalidateQueries({ queryKey: protectedQueryKeys.teamIterations(userId, access.teamId) }),
    client.invalidateQueries({ queryKey: ["protected", userId, "team-board", access.teamId] }),
  ]);
  if (packages.isPending || iterations.isPending || people.isPending) return <PageState kind="loading" title="Loading team planning" />;
  if (packages.isError || iterations.isError || people.isError) return <PageState action={<button className="button" onClick={() => { void packages.refetch(); void iterations.refetch(); void people.refetch(); }}>Try again</button>} kind="error" title="Team planning could not be loaded" />;
  const manager = Boolean(access.grantId && access.permissions.includes("BOARD"));
  return (
    <div className="planning-page page-stack">
      <header className="planning-heading"><span>Delivery context</span><h2>Team planning</h2><p>Shape how the team delivers: time-box work into iterations, break delivery into packages, and reserve real calendar capacity. Camunda remains authoritative for every customer request stage.</p></header>
      <PlanningPulse iterations={iterations.data.items} packages={packages.data.items} />
      <PlanningEnhancements access={access} session={session} />
      <section className="planning-iterations">
        <header className="planning-section-heading"><span>Time-boxes</span><h2>Iterations</h2><p>Optional windows that group packages towards a shared goal.</p></header>
        <IterationRegister access={access} items={iterations.data.items} onChanged={refresh} session={session} />
        {manager ? <IterationForm access={access} onChanged={refresh} session={session} /> : null}
      </section>
      <section className="planning-layout">
        <div className="package-register">
          <header><span>Backlog and delivery</span><h2>Work packages</h2></header>
          {packages.data.items.length ? <PackageBrowser items={packages.data.items} onSelect={setSelectedId} selectedId={selected?.id ?? ""} /> : <PageState kind="empty" title="No work packages">Create one from the Board view.</PageState>}
          {selected ? <PackageDetail item={selected} /> : null}
          {selected && manager ? <WorkPackageEditForm access={access} item={selected} items={packages.data.items} iterations={iterations.data.items} key={selected.id} members={people.data.items} onUpdated={() => { void refresh(); }} session={session} /> : null}
        </div>
        {selected ? <ReservationForm access={access} item={selected} members={people.data.items.filter((item) => item.state === "CURRENT")} onChanged={refresh} session={session} /> : null}
      </section>
    </div>
  );
}

function PlanningPulse({ iterations, packages }: { iterations: Iteration[]; packages: WorkPackage[] }) {
  const active = iterations.find((item) => item.status === "ACTIVE");
  const daysLeft = active ? Math.max(0, Math.ceil((new Date(active.endsOn).getTime() - Date.now()) / 86_400_000)) : null;
  const open = packages.filter((item) => !["DONE", "CANCELLED"].includes(item.status));
  const blocked = open.filter((item) => item.status === "BLOCKED").length;
  const remainingHours = Math.round(open.reduce((total, item) => total + item.remainingEffortMinutes, 0) / 6) / 10;
  const reservedHours = Math.round(packages.flatMap((item) => item.reservations).filter((item) => item.status === "ACTIVE").reduce((total, item) => total + item.minutes, 0) / 6) / 10;
  return (
    <section aria-label="Planning pulse" className="planning-pulse">
      <div><span>Active iteration</span><strong>{active ? active.name : "None"}</strong><small>{active ? `${daysLeft} day${daysLeft === 1 ? "" : "s"} remaining` : "Create one to time-box delivery"}</small></div>
      <div><span>Open packages</span><strong>{open.length}</strong><small>{packages.length - open.length} finished or cancelled</small></div>
      <div className={blocked ? "planning-pulse--attention" : undefined}><span>Blocked</span><strong>{blocked}</strong><small>{blocked ? "Needs an unblocking decision" : "Nothing is blocked"}</small></div>
      <div><span>Remaining effort</span><strong>{remainingHours}h</strong><small>Across open packages</small></div>
      <div><span>Reserved capacity</span><strong>{reservedHours}h</strong><small>Active calendar reservations</small></div>
    </section>
  );
}

function PackageBrowser({ items, onSelect, selectedId }: { items: WorkPackage[]; onSelect: (id: string) => void; selectedId: string }) {
  return (
    <ul aria-label="Work package list" className="package-browser">
      {items.map((item) => (
        <li key={item.id}>
          <button aria-pressed={item.id === selectedId} onClick={() => onSelect(item.id)} type="button">
            <span className={`package-chip package-chip--${item.status.toLowerCase()}`}>{boardLabel(item.status)}</span>
            <strong>{item.title}</strong>
            <small>{item.ownerDisplayName} · due {item.dueOn} · {item.estimatePoints} points · {boardLabel(item.priority)}</small>
          </button>
        </li>
      ))}
    </ul>
  );
}

function IterationForm({ access, onChanged, session }: { access: TeamWorkspaceAccess; onChanged: () => Promise<unknown>; session: Session }) {
  const [name, setName] = useState(""); const [goal, setGoal] = useState(""); const [start, setStart] = useState(""); const [end, setEnd] = useState("");
  const mutation = useMutation({ mutationFn: () => {
    if (!access.grantId) throw new Error("Iteration authority is required.");
    return boardApi.createIteration(access.teamId, { grantId: access.grantId, name, goal, startsOn: start, endsOn: end }, session.csrfToken);
  }, onSuccess: () => { setName(""); setGoal(""); setStart(""); setEnd(""); void onChanged(); } });
  return <section className="iteration-form"><header><span>Optional time-box</span><h2>Create iteration</h2></header><form onSubmit={(event) => { event.preventDefault(); mutation.mutate(); }}><Required label="Name"><input minLength={3} onChange={(event) => setName(event.target.value)} required value={name} /></Required><Required label="Goal"><input onChange={(event) => setGoal(event.target.value)} required value={goal} /></Required><Required label="Starts"><input onChange={(event) => setStart(event.target.value)} required type="date" value={start} /></Required><Required label="Ends"><input min={start} onChange={(event) => setEnd(event.target.value)} required type="date" value={end} /></Required><button className="button" disabled={mutation.isPending} type="submit">Create iteration</button></form>{mutation.isError ? <p role="alert">{message(mutation.error)}</p> : null}</section>;
}

function IterationRegister({ access, items, onChanged, session }: { access: TeamWorkspaceAccess; items: Iteration[]; onChanged: () => Promise<unknown>; session: Session }) {
  const [summary, setSummary] = useState(""); const [selected, setSelected] = useState("");
  const active = items.find((item) => item.status === "ACTIVE");
  const mutation = useMutation({ mutationFn: () => {
    const item = items.find((value) => value.id === selected);
    if (!access.grantId || !item) throw new Error("Select an iteration to close.");
    return boardApi.closeIteration(access.teamId, item.id, { grantId: access.grantId, expectedVersion: item.version, completionSummary: summary }, session.csrfToken);
  }, onSuccess: () => { setSummary(""); setSelected(""); void onChanged(); } });
  return <section className="iteration-register">
    {active ? <article className="iteration-hero"><span>Now running</span><h3>{active.name}</h3><p>{active.goal}</p><small>{active.startsOn} to {active.endsOn}</small></article> : null}
    <div className="team-table-wrap"><table className="team-table"><caption>Team iterations</caption><thead><tr><th>Name</th><th>Goal</th><th>Window</th><th>Status</th></tr></thead><tbody>{items.map((item) => <tr key={item.id}><th>{item.name}</th><td>{item.goal}</td><td>{item.startsOn} to {item.endsOn}</td><td><span className={`package-chip package-chip--${item.status.toLowerCase()}`}>{boardLabel(item.status)}</span></td></tr>)}</tbody></table></div>
    {access.grantId ? <form onSubmit={(event) => { event.preventDefault(); mutation.mutate(); }}><Required label="Iteration"><select onChange={(event) => setSelected(event.target.value)} required value={selected}><option value="">Select active iteration</option>{items.filter((item) => item.status !== "CLOSED").map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Required><Required label="Completion summary"><input minLength={1} onChange={(event) => setSummary(event.target.value)} required value={summary} /></Required><button className="button" disabled={mutation.isPending} type="submit">Close iteration</button></form> : null}
    {mutation.isError ? <p role="alert">{message(mutation.error)}</p> : null}
  </section>;
}

function PackageDetail({ item }: { item: WorkPackage }) {
  return <article className="package-detail">
    <div className="package-detail__heading">
      <span className={`package-chip package-chip--${item.status.toLowerCase()}`}>{boardLabel(item.status)}</span>
      <span className="package-detail__priority">{item.priority}</span>
      {item.linkedRequestId ? <Link className="package-detail__request" to={`/requests/${item.linkedRequestId}`}>Open linked request</Link> : null}
    </div>
    <h3>{item.title}</h3><p>{item.description}</p>
    <dl><div><dt>Owner</dt><dd>{item.ownerDisplayName}</dd></div><div><dt>Estimate</dt><dd>{item.estimatePoints} points</dd></div><div><dt>Remaining</dt><dd>{item.remainingEffortMinutes} minutes</dd></div><div><dt>Due</dt><dd>{item.dueOn}</dd></div><div><dt>Contributors</dt><dd>{item.contributors.map((value) => value.displayName).join(", ") || "None"}</dd></div><div><dt>Dependencies</dt><dd>{item.dependencyIds.join(", ") || "None"}</dd></div></dl>
    <section><h4>Acceptance criteria</h4><p>{item.acceptanceCriteria}</p><h4>Blockers</h4><p>{item.blockers}</p></section>
    <ol className="package-activity">{item.activities.map((activity) => <li key={activity.id}><time>{new Date(activity.createdAt).toLocaleString("en-GB")}</time><span>{activity.summary} · {activity.actorDisplayName}</span></li>)}</ol>
  </article>;
}

function ReservationForm({ access, item, members, onChanged, session }: { access: TeamWorkspaceAccess; item: WorkPackage; members: Array<{ accountId: string; displayName: string }>; onChanged: () => Promise<unknown>; session: Session }) {
  const [userId, setUserId] = useState(""); const [start, setStart] = useState(() => localDateTimeInputValue(new Date(Date.now() + 86_400_000))); const [end, setEnd] = useState(() => localDateTimeInputValue(new Date(Date.now() + 90_000_000))); const [reason, setReason] = useState("");
  const create = useMutation({ mutationFn: () => {
    return boardApi.reserve(access.teamId, item.id, item.version, { grantId: access.grantId, userId, startsAt: new Date(start).toISOString(), endsAt: new Date(end).toISOString(), reason }, session.csrfToken);
  }, onSuccess: () => { setReason(""); void onChanged(); } });
  const cancel = useMutation({ mutationFn: (reservation: WorkPackage["reservations"][number]) => {
    return boardApi.cancelReservation(access.teamId, item.id, reservation.id, item.version, { grantId: access.grantId, expectedVersion: reservation.version, reason: "The team deliberately released this capacity after replanning." }, session.csrfToken);
  }, onSuccess: onChanged });
  return <div className="reservation-panel"><header><span>Calendar-backed capacity</span><h2>Reserve effort</h2></header><form onSubmit={(event) => { event.preventDefault(); create.mutate(); }}><Required label="Person"><select onChange={(event) => setUserId(event.target.value)} required value={userId}><option value="">Select a team member</option>{members.map((member) => <option key={member.accountId} value={member.accountId}>{member.displayName}</option>)}</select></Required><Required label="Starts"><input onChange={(event) => setStart(event.target.value)} required type="datetime-local" value={start} /></Required><Required label="Ends"><input min={start} onChange={(event) => setEnd(event.target.value)} required type="datetime-local" value={end} /></Required><Required label="Reason"><textarea minLength={10} onChange={(event) => setReason(event.target.value)} required value={reason} /></Required><button className="button button--primary" disabled={create.isPending} type="submit">Reserve capacity</button></form>{create.isError || cancel.isError ? <p role="alert">{message(create.error ?? cancel.error)}</p> : null}<ul className="reservation-list">{item.reservations.map((reservation) => <li key={reservation.id}><span>{reservation.userDisplayName}<small>{reservation.minutes} minutes · {reservation.status}</small></span>{reservation.status === "ACTIVE" ? <button className="button button--danger" disabled={cancel.isPending} onClick={() => cancel.mutate(reservation)} type="button">Cancel</button> : null}</li>)}</ul></div>;
}

function Required({ children, label }: { children: ReactNode; label: string }) { return <label className="form-field">{label}<span className="field-hint">Required</span>{children}</label>; }
function message(error: Error | null) { return error instanceof ApiError ? error.message : error?.message ?? "The planning change could not be saved."; }
