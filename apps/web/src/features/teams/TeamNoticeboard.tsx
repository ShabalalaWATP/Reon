import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ApiError, api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type {
  TeamWorkspaceAccess,
  WorkspaceRecord,
  WorkspaceRecordList,
} from "../../lib/api/teamTypes";
import { useAuth } from "../../lib/auth/AuthProvider";
import { formatDate } from "../../lib/status";

const kindLabels: Record<WorkspaceRecord["kind"], string> = {
  DESCRIPTION: "Description",
  HANDOVER: "Notice",
  RISK: "Risk",
  BLOCKER: "Blocker",
  DECISION: "Decision",
  LINK: "Link",
};

export function TeamNoticeboard({ access, userId }: { access: TeamWorkspaceAccess; userId: string }) {
  const { session } = useAuth();
  const client = useQueryClient();
  const queryKey = protectedQueryKeys.teamRecords(userId, access.teamId);
  const records = useQuery({ queryKey, queryFn: () => api.workspaceRecords(access.teamId) });
  const canManage = Boolean(access.grantId && access.permissions.includes("ROSTER"));
  const csrfToken = session!.csrfToken;
  const saveList = (list: WorkspaceRecordList) => client.setQueryData(queryKey, list);
  const open = (records.data?.items ?? [])
    .filter((item) => item.status === "OPEN")
    .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt));
  const notices = open.filter((item) => item.kind !== "LINK");
  const links = open.filter((item) => item.kind === "LINK");
  return (
    <section aria-labelledby="team-noticeboard-title" className="workspace-records team-noticeboard">
      <header>
        <span>Shared team space</span>
        <h2 id="team-noticeboard-title">Noticeboard and pinned links</h2>
        <p>{canManage
          ? "Standing notices and useful links for everyone in this workspace. Posting and archiving are recorded with your name."
          : "Standing notices and useful links kept current by this workspace's Managers."}</p>
      </header>
      {records.isPending ? <p className="inline-empty">Loading the noticeboard…</p> : null}
      {records.isError ? <p className="inline-unavailable">Noticeboard unavailable</p> : null}
      {records.data ? (
        <div className="workspace-collaboration">
          <div className="team-noticeboard__column">
            <h3 id="team-notices-title">Notices</h3>
            {notices.length ? (
              <ol aria-labelledby="team-notices-title">
                {notices.map((record) => <RecordItem access={access} canManage={canManage} csrfToken={csrfToken} key={record.id} onSaved={saveList} record={record} />)}
              </ol>
            ) : <p className="inline-empty">No standing notices.</p>}
            {canManage ? <NoticeForm access={access} csrfToken={csrfToken} onSaved={saveList} /> : null}
          </div>
          <aside className="team-noticeboard__column">
            <h3 id="team-links-title">Pinned links</h3>
            {links.length ? (
              <ul aria-labelledby="team-links-title">
                {links.map((record) => <RecordItem access={access} canManage={canManage} csrfToken={csrfToken} key={record.id} onSaved={saveList} record={record} />)}
              </ul>
            ) : <p className="inline-empty">No pinned links.</p>}
            {canManage ? <LinkForm access={access} csrfToken={csrfToken} onSaved={saveList} /> : null}
          </aside>
        </div>
      ) : null}
    </section>
  );
}

type MutationProps = {
  access: TeamWorkspaceAccess;
  csrfToken: string;
  onSaved: (list: WorkspaceRecordList) => void;
};

function RecordItem({ access, canManage, csrfToken, onSaved, record }: MutationProps & { canManage: boolean; record: WorkspaceRecord }) {
  const [archiving, setArchiving] = useState(false);
  const [resolution, setResolution] = useState("");
  const resolve = useMutation({
    mutationFn: () => api.resolveWorkspaceRecord(access.teamId, record.id, {
      grantId: access.grantId!,
      expectedVersion: record.version,
      resolution: resolution.trim(),
    }, csrfToken),
    onSuccess: onSaved,
  });
  const link = record.kind === "LINK" && record.url;
  const archiveLabel = record.kind === "LINK" ? "Remove" : "Archive";
  return (
    <li className="workspace-record">
      <header><span>{kindLabels[record.kind]}</span><small>{record.createdByDisplayName} · {formatDate(record.updatedAt, true)}</small></header>
      <h4>{link ? <a href={record.url!} rel="noopener noreferrer" target="_blank">{record.title}</a> : record.title}</h4>
      <p>{record.body}</p>
      {canManage && !archiving ? <button className="button button--quiet workspace-record__action" onClick={() => setArchiving(true)} type="button">{archiveLabel} {record.title}</button> : null}
      {canManage && archiving ? (
        <form onSubmit={(event) => { event.preventDefault(); resolve.mutate(); }}>
          <label className="form-field">Reason<span className="field-hint">Required, at least 10 characters. Kept in the workspace record.</span>
            <textarea maxLength={1000} minLength={10} onChange={(event) => setResolution(event.target.value)} required rows={2} value={resolution} />
          </label>
          {resolve.isError ? <p className="form-banner form-banner--error" role="alert">{errorText(resolve.error)}</p> : null}
          <div className="workspace-record__actions">
            <button className="button button--primary" disabled={resolve.isPending || resolution.trim().length < 10} type="submit">{resolve.isPending ? "Saving…" : `Confirm ${archiveLabel.toLowerCase()}`}</button>
            <button className="button button--quiet" onClick={() => setArchiving(false)} type="button">Keep</button>
          </div>
        </form>
      ) : null}
    </li>
  );
}

function NoticeForm({ access, csrfToken, onSaved }: MutationProps) {
  const [openForm, setOpenForm] = useState(false);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const create = useMutation({
    mutationFn: () => api.createWorkspaceRecord(access.teamId, {
      grantId: access.grantId!,
      kind: "HANDOVER",
      title: title.trim(),
      body: body.trim(),
    }, csrfToken),
    onSuccess: (list) => { setTitle(""); setBody(""); setOpenForm(false); onSaved(list); },
  });
  if (!openForm) return <button className="button button--quiet team-noticeboard__open-form" onClick={() => setOpenForm(true)} type="button">Post a notice</button>;
  return (
    <form className="team-noticeboard__form" onSubmit={(event) => { event.preventDefault(); create.mutate(); }}>
      <label className="form-field">Notice title<input maxLength={160} minLength={3} onChange={(event) => setTitle(event.target.value)} required value={title} /></label>
      <label className="form-field">Notice detail<span className="field-hint">Visible to everyone with this workspace.</span>
        <textarea maxLength={4000} minLength={3} onChange={(event) => setBody(event.target.value)} required rows={3} value={body} />
      </label>
      {create.isError ? <p className="form-banner form-banner--error" role="alert">{errorText(create.error)}</p> : null}
      <div className="workspace-record__actions">
        <button className="button button--primary" disabled={create.isPending || title.trim().length < 3 || body.trim().length < 3} type="submit">{create.isPending ? "Posting…" : "Post notice"}</button>
        <button className="button button--quiet" onClick={() => setOpenForm(false)} type="button">Cancel</button>
      </div>
    </form>
  );
}

function LinkForm({ access, csrfToken, onSaved }: MutationProps) {
  const [openForm, setOpenForm] = useState(false);
  const [title, setTitle] = useState("");
  const [url, setUrl] = useState("");
  const [body, setBody] = useState("");
  const create = useMutation({
    mutationFn: () => api.createWorkspaceRecord(access.teamId, {
      grantId: access.grantId!,
      kind: "LINK",
      title: title.trim(),
      body: body.trim(),
      url: url.trim(),
    }, csrfToken),
    onSuccess: (list) => { setTitle(""); setUrl(""); setBody(""); setOpenForm(false); onSaved(list); },
  });
  if (!openForm) return <button className="button button--quiet team-noticeboard__open-form" onClick={() => setOpenForm(true)} type="button">Add a link</button>;
  return (
    <form className="team-noticeboard__form" onSubmit={(event) => { event.preventDefault(); create.mutate(); }}>
      <label className="form-field">Link title<input maxLength={160} minLength={3} onChange={(event) => setTitle(event.target.value)} required value={title} /></label>
      <label className="form-field">Link URL<span className="field-hint">Public HTTPS addresses only.</span>
        <input maxLength={500} onChange={(event) => setUrl(event.target.value)} placeholder="https://" required type="url" value={url} />
      </label>
      <label className="form-field">Short description<textarea maxLength={4000} minLength={3} onChange={(event) => setBody(event.target.value)} required rows={2} value={body} /></label>
      {create.isError ? <p className="form-banner form-banner--error" role="alert">{errorText(create.error)}</p> : null}
      <div className="workspace-record__actions">
        <button className="button button--primary" disabled={create.isPending || title.trim().length < 3 || body.trim().length < 3 || !url.trim().startsWith("https://")} type="submit">{create.isPending ? "Adding…" : "Add link"}</button>
        <button className="button button--quiet" onClick={() => setOpenForm(false)} type="button">Cancel</button>
      </div>
    </form>
  );
}

function errorText(error: Error | null) {
  if (error instanceof ApiError) return error.message;
  return "The noticeboard change could not be saved. Refresh and try again.";
}
