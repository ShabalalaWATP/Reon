import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { PageState } from "../../components/PageState";
import { api, ApiError } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { TeamMember, TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import { useAuth } from "../../lib/auth/AuthProvider";

export function TeamPeoplePanel({ access, userId }: { access: TeamWorkspaceAccess; userId: string }) {
  const { session } = useAuth();
  const client = useQueryClient();
  const [mode, setMode] = useState<"add" | "transfer">("add");
  const [selectedId, setSelectedId] = useState("");
  const [reason, setReason] = useState("");
  const [effectiveFrom, setEffectiveFrom] = useState("");
  const canManage = access.permissions.includes("ROSTER") && Boolean(access.grantId);
  const people = useQuery({ queryKey: protectedQueryKeys.teamPeople(userId, access.teamId), queryFn: () => api.teamPeople(access.teamId) });
  const eligible = useQuery({ queryKey: protectedQueryKeys.teamEligibleAnalysts(userId, access.teamId), queryFn: () => api.eligibleRosterAnalysts(access.teamId, access.grantId ?? ""), enabled: canManage });
  const mutation = useMutation({
    mutationFn: async () => {
      const analyst = eligible.data?.items.find((item) => item.accountId === selectedId);
      if (!session || !analyst || !access.grantId) throw new Error("Select a compatible Member.");
      if (mode === "add") return api.addTeamMember(access.teamId, { grantId: access.grantId, analystId: analyst.accountId, reason }, session.csrfToken);
      if (!analyst.currentMembershipId || analyst.currentMembershipVersion === null || !effectiveFrom) throw new Error("Complete the transfer details.");
      return api.transferTeamMember(access.teamId, { grantId: access.grantId, analystId: analyst.accountId, reason, currentMembershipId: analyst.currentMembershipId, expectedVersion: analyst.currentMembershipVersion, effectiveFrom: new Date(effectiveFrom).toISOString() }, session.csrfToken);
    },
    onSuccess: (data) => { client.setQueryData(protectedQueryKeys.teamPeople(userId, access.teamId), data); setSelectedId(""); setReason(""); setEffectiveFrom(""); void client.invalidateQueries({ queryKey: protectedQueryKeys.teamEligibleAnalysts(userId, access.teamId) }); },
  });
  if (people.isPending) return <PageState kind="loading" title="Loading team people" />;
  if (people.isError) return <PageState action={<button className="button" onClick={() => void people.refetch()}>Try again</button>} kind="error" title="Team people could not be loaded" />;
  const options = (eligible.data?.items ?? []).filter((item) => mode === "add" ? item.currentTeamId === null : item.currentTeamId !== null && item.currentTeamId !== access.teamId);
  return (
    <div className="team-people-layout">
      <section aria-labelledby="team-people-title" className="team-register">
        <header><span>Effective membership</span><h2 id="team-people-title">People</h2><p>Every workspace has named Managers and Members. Current, scheduled and ended records remain visible as history.</p></header>
        <PeopleTable access={access} items={people.data.items} userId={userId} />
      </section>
      {canManage ? (
        <aside className="roster-control">
          <span>Manager action</span><h2>Change roster</h2>
          <div className="roster-mode"><button aria-pressed={mode === "add"} onClick={() => { setMode("add"); setSelectedId(""); }} type="button">Add unassigned</button><button aria-pressed={mode === "transfer"} onClick={() => { setMode("transfer"); setSelectedId(""); }} type="button">Schedule transfer</button></div>
          {eligible.isPending ? <p className="inline-loading">Loading Members…</p> : eligible.isError ? (
            <div className="form-banner form-banner--error" role="alert">
              <p>Eligible Members could not be loaded.</p>
              <button className="button" onClick={() => void eligible.refetch()} type="button">Try again</button>
            </div>
          ) : (
            <form onSubmit={(event) => { event.preventDefault(); mutation.mutate(); }}>
              <label className="form-field">Member<span className="field-hint">Required</span><select onChange={(event) => setSelectedId(event.target.value)} required value={selectedId}><option value="">Select a compatible Member</option>{options.map((item) => <option key={item.accountId} value={item.accountId}>{item.displayName}{item.currentTeamName ? ` · ${item.currentTeamName}` : " · Unassigned"}</option>)}</select></label>
              {mode === "transfer" ? <label className="form-field">Effective date and time<span className="field-hint">Required</span><input min={localNow()} onChange={(event) => setEffectiveFrom(event.target.value)} required type="datetime-local" value={effectiveFrom} /></label> : null}
              <label className="form-field">Reason<span className="field-hint">Required, 10–500 characters</span><textarea maxLength={500} minLength={10} onChange={(event) => setReason(event.target.value)} required rows={4} value={reason} /></label>
              {mutation.isError ? <p className="form-banner form-banner--error" role="alert">{errorMessage(mutation.error)}</p> : null}
              <button className="button button--primary" disabled={mutation.isPending || options.length === 0} type="submit">{mutation.isPending ? "Saving…" : mode === "add" ? "Add Member" : "Confirm transfer"}</button>
            </form>
          )}
        </aside>
      ) : null}
    </div>
  );
}

function PeopleTable({ access, items, userId }: { access: TeamWorkspaceAccess; items: TeamMember[]; userId: string }) {
  return <div className="team-table-wrap"><table className="team-table"><caption>Workspace membership history</caption><thead><tr><th scope="col">Person</th><th scope="col">Position</th><th scope="col">State</th><th scope="col">Effective</th><th scope="col">Active work</th><th scope="col">Action</th></tr></thead><tbody>{items.map((member) => <PersonRow access={access} key={member.membershipId} member={member} userId={userId} />)}</tbody></table></div>;
}

function PersonRow({ access, member, userId }: { access: TeamWorkspaceAccess; member: TeamMember; userId: string }) {
  const { session } = useAuth(); const client = useQueryClient(); const [ending, setEnding] = useState(false); const [reason, setReason] = useState("");
  const mutation = useMutation({ mutationFn: () => api.endTeamMembership(access.teamId, member.membershipId, { grantId: access.grantId ?? "", expectedVersion: member.version, reason }, session?.csrfToken ?? ""), onSuccess: (data) => { client.setQueryData(protectedQueryKeys.teamPeople(userId, access.teamId), data); setEnding(false); } });
  const canEnd = access.permissions.includes("ROSTER") && (member.workspacePosition ?? (member.role === "DELIVERY_TEAM_LEAD" ? "MANAGER" : "MEMBER")) === "MEMBER" && member.state === "CURRENT";
  return <><tr><th scope="row"><strong>{member.displayName}</strong>{member.endReason ? <small>{member.endReason}</small> : null}</th><td>{member.workspacePosition ?? (member.role === "DELIVERY_TEAM_LEAD" ? "MANAGER" : "MEMBER")}</td><td><span className={`membership-state membership-state--${member.state.toLowerCase()}`}>{member.state.toLowerCase()}</span></td><td>{formatDate(member.effectiveFrom)}{member.effectiveUntil ? ` to ${formatDate(member.effectiveUntil)}` : " onwards"}</td><td>{member.activeWorkCount}</td><td>{canEnd ? <button className="button button--quiet" disabled={member.activeWorkCount > 0} onClick={() => setEnding(!ending)} type="button">End membership</button> : "Not applicable"}</td></tr>{ending ? <tr className="end-membership-row"><td colSpan={6}><form onSubmit={(event) => { event.preventDefault(); mutation.mutate(); }}><label className="form-field">Reason for ending membership<span className="field-hint">Required</span><textarea minLength={10} onChange={(event) => setReason(event.target.value)} required value={reason} /></label>{mutation.isError ? <p role="alert">{errorMessage(mutation.error)}</p> : null}<button className="button button--danger" disabled={mutation.isPending} type="submit">Confirm end</button></form></td></tr> : null}</>;
}

function formatDate(value: string) { return new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" }).format(new Date(value)); }
function localNow() { const value = new Date(Date.now() + 60_000); return new Date(value.getTime() - value.getTimezoneOffset() * 60_000).toISOString().slice(0, 16); }
function errorMessage(error: Error) { return error instanceof ApiError ? error.message : error.message || "The roster change could not be saved."; }
