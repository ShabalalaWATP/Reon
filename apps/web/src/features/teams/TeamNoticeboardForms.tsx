import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "../../lib/api/client";
import type { TeamWorkspaceAccess, WorkspaceRecordList } from "../../lib/api/teamTypes";
import { workspaceRecordErrorText } from "./workspaceRecordModel";

export type WorkspaceMutationProps = {
  access: TeamWorkspaceAccess;
  csrfToken: string;
  onSaved: (list: WorkspaceRecordList) => void;
};

export function TeamNoticeForm({ access, csrfToken, onSaved }: WorkspaceMutationProps) {
  const [openForm, setOpenForm] = useState(false);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const create = useMutation({
    mutationFn: () =>
      api.createWorkspaceRecord(
        access.teamId,
        {
          body: body.trim(),
          grantId: access.grantId!,
          kind: "HANDOVER",
          title: title.trim(),
        },
        csrfToken,
      ),
    onSuccess: (list) => {
      setTitle("");
      setBody("");
      setOpenForm(false);
      onSaved(list);
    },
  });
  if (!openForm) return <OpenFormButton label="Post a notice" open={() => setOpenForm(true)} />;
  return (
    <form
      className="team-noticeboard__form"
      onSubmit={(event) => {
        event.preventDefault();
        create.mutate();
      }}
    >
      <label className="form-field">
        Notice title
        <input
          maxLength={160}
          minLength={3}
          onChange={(event) => setTitle(event.target.value)}
          required
          value={title}
        />
      </label>
      <label className="form-field">
        Notice detail<span className="field-hint">Visible to everyone with this workspace.</span>
        <textarea
          maxLength={4000}
          minLength={3}
          onChange={(event) => setBody(event.target.value)}
          required
          rows={3}
          value={body}
        />
      </label>
      {create.isError ? <MutationError error={create.error} /> : null}
      <FormActions
        cancel={() => setOpenForm(false)}
        disabled={create.isPending || title.trim().length < 3 || body.trim().length < 3}
        label={create.isPending ? "Posting…" : "Post notice"}
      />
    </form>
  );
}

export function TeamNoticeboardLinkForm({ access, csrfToken, onSaved }: WorkspaceMutationProps) {
  const [openForm, setOpenForm] = useState(false);
  const [title, setTitle] = useState("");
  const [url, setUrl] = useState("");
  const [body, setBody] = useState("");
  const create = useMutation({
    mutationFn: () =>
      api.createWorkspaceRecord(
        access.teamId,
        {
          body: body.trim(),
          grantId: access.grantId!,
          kind: "LINK",
          title: title.trim(),
          url: url.trim(),
        },
        csrfToken,
      ),
    onSuccess: (list) => {
      setTitle("");
      setUrl("");
      setBody("");
      setOpenForm(false);
      onSaved(list);
    },
  });
  if (!openForm) return <OpenFormButton label="Add a link" open={() => setOpenForm(true)} />;
  const disabled =
    create.isPending ||
    title.trim().length < 3 ||
    body.trim().length < 3 ||
    !url.trim().startsWith("https://");
  return (
    <form
      className="team-noticeboard__form"
      onSubmit={(event) => {
        event.preventDefault();
        create.mutate();
      }}
    >
      <label className="form-field">
        Link title
        <input
          maxLength={160}
          minLength={3}
          onChange={(event) => setTitle(event.target.value)}
          required
          value={title}
        />
      </label>
      <label className="form-field">
        Link URL<span className="field-hint">Public HTTPS addresses only.</span>
        <input
          maxLength={500}
          onChange={(event) => setUrl(event.target.value)}
          placeholder="https://"
          required
          type="url"
          value={url}
        />
      </label>
      <label className="form-field">
        Short description
        <textarea
          maxLength={4000}
          minLength={3}
          onChange={(event) => setBody(event.target.value)}
          required
          rows={2}
          value={body}
        />
      </label>
      {create.isError ? <MutationError error={create.error} /> : null}
      <FormActions
        cancel={() => setOpenForm(false)}
        disabled={disabled}
        label={create.isPending ? "Adding…" : "Add link"}
      />
    </form>
  );
}

function OpenFormButton({ label, open }: { label: string; open: () => void }) {
  return (
    <button
      className="button button--quiet team-noticeboard__open-form"
      onClick={open}
      type="button"
    >
      {label}
    </button>
  );
}

function FormActions({
  cancel,
  disabled,
  label,
}: {
  cancel: () => void;
  disabled: boolean;
  label: string;
}) {
  return (
    <div className="workspace-record__actions">
      <button className="button button--primary" disabled={disabled} type="submit">
        {label}
      </button>
      <button className="button button--quiet" onClick={cancel} type="button">
        Cancel
      </button>
    </div>
  );
}

function MutationError({ error }: { error: Error }) {
  return (
    <p className="form-banner form-banner--error" role="alert">
      {workspaceRecordErrorText(error)}
    </p>
  );
}
