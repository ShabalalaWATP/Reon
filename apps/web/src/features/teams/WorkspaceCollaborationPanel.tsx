import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { PageState } from "../../components/PageState";
import { api, ApiError } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { TeamWorkspaceAccess, WorkspaceRecord, WorkspaceRecordKind } from "../../lib/api/teamTypes";
import { useAuth } from "../../lib/auth/AuthProvider";

const kinds: WorkspaceRecordKind[] = ["HANDOVER", "RISK", "BLOCKER", "DECISION", "LINK", "DESCRIPTION"];

export function WorkspaceCollaborationPanel({ access, userId }: { access: TeamWorkspaceAccess; userId: string }) {
  const { session } = useAuth();
  const client = useQueryClient();
  const key = protectedQueryKeys.workspaceRecords(userId, access.teamId);
  const query = useQuery({ queryKey: key, queryFn: () => api.workspaceRecords(access.teamId) });
  const [kind, setKind] = useState<WorkspaceRecordKind>("HANDOVER");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [url, setUrl] = useState("");
  const canManage = Boolean(access.grantId && access.permissions.includes("ROSTER"));
  const create = useMutation({
    mutationFn: () => {
      if (!session || !access.grantId) throw new Error("Manager authority is required.");
      return api.createWorkspaceRecord(access.teamId, { grantId: access.grantId, kind, title, body, url: kind === "LINK" ? url : null }, session.csrfToken);
    },
    onSuccess: (data) => { client.setQueryData(key, data); setTitle(""); setBody(""); setUrl(""); },
  });
  if (query.isPending) return <PageState kind="loading" title="Loading workspace records" />;
  if (query.isError) return <PageState action={<button className="button" onClick={() => void query.refetch()}>Try again</button>} kind="error" title="Workspace records could not be loaded" />;
  return <div className="workspace-collaboration">
    <section className="workspace-records" aria-labelledby="workspace-records-title">
      <header><span>Shared operational memory</span><h2 id="workspace-records-title">Handover and decisions</h2><p>Short, bounded records support the team without becoming a second workflow or document store.</p></header>
      {query.data.items.length ? <ol>{query.data.items.map((record) => <Record access={access} item={record} key={record.id} queryKey={key} />)}</ol> : <PageState kind="empty" title="No workspace records">Managers can add handover notes, risks, blockers, decisions and useful links.</PageState>}
    </section>
    {canManage ? <aside className="workspace-record-form"><span>Manager action</span><h2>Add shared context</h2><form onSubmit={(event) => { event.preventDefault(); create.mutate(); }}>
      <label className="form-field">Record type<span className="field-hint">Required</span><select onChange={(event) => setKind(event.target.value as WorkspaceRecordKind)} required value={kind}>{kinds.map((item) => <option key={item} value={item}>{label(item)}</option>)}</select></label>
      <label className="form-field">Title<span className="field-hint">Required</span><input maxLength={160} minLength={3} onChange={(event) => setTitle(event.target.value)} required value={title} /></label>
      <label className="form-field">Detail<span className="field-hint">Required</span><textarea maxLength={4000} minLength={3} onChange={(event) => setBody(event.target.value)} required rows={6} value={body} /></label>
      {kind === "LINK" ? <label className="form-field">HTTPS link<span className="field-hint">Required</span><input maxLength={500} onChange={(event) => setUrl(event.target.value)} pattern="https://.*" required type="url" value={url} /></label> : null}
      {create.isError ? <p className="form-banner form-banner--error" role="alert">{message(create.error)}</p> : null}
      <button className="button button--primary" disabled={create.isPending} type="submit">{create.isPending ? "Saving…" : "Add record"}</button>
    </form></aside> : null}
  </div>;
}

function Record({ access, item, queryKey }: { access: TeamWorkspaceAccess; item: WorkspaceRecord; queryKey: readonly unknown[] }) {
  const { session } = useAuth();
  const client = useQueryClient();
  const [resolution, setResolution] = useState("");
  const canResolve = item.status === "OPEN" && Boolean(access.grantId && access.permissions.includes("ROSTER"));
  const mutation = useMutation({
    mutationFn: () => {
      if (!session || !access.grantId) throw new Error("Manager authority is required.");
      return api.resolveWorkspaceRecord(access.teamId, item.id, { grantId: access.grantId, expectedVersion: item.version, resolution }, session.csrfToken);
    },
    onSuccess: (data) => client.setQueryData(queryKey, data),
  });
  return <li className={`workspace-record workspace-record--${item.status.toLowerCase()}`}><header><span>{label(item.kind)}</span><strong>{item.title}</strong><small>{item.createdByDisplayName} · {new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" }).format(new Date(item.updatedAt))}</small></header><p>{item.body}</p>{item.url ? <a href={item.url} rel="noreferrer" target="_blank">Open useful link</a> : null}{item.resolution ? <p><strong>Resolution:</strong> {item.resolution}</p> : null}{canResolve ? <form onSubmit={(event) => { event.preventDefault(); mutation.mutate(); }}><label className="form-field">Resolution<span className="field-hint">Required</span><textarea maxLength={1000} minLength={10} onChange={(event) => setResolution(event.target.value)} required value={resolution} /></label>{mutation.isError ? <p role="alert">{message(mutation.error)}</p> : null}<button className="button button--quiet" disabled={mutation.isPending} type="submit">Resolve record</button></form> : null}</li>;
}

function label(value: string) { return value.replaceAll("_", " ").toLowerCase().replace(/^./, (first) => first.toUpperCase()); }
function message(error: Error) { return error instanceof ApiError ? error.message : error.message || "The workspace record could not be saved."; }
