import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "../../lib/api/client";
import type { WorkspaceRecord } from "../../lib/api/teamTypes";
import { formatDate } from "../../lib/status";
import type { WorkspaceMutationProps } from "./TeamNoticeboardForms";
import { workspaceRecordErrorText } from "./workspaceRecordModel";

const kindLabels: Record<WorkspaceRecord["kind"], string> = {
  DESCRIPTION: "Description",
  HANDOVER: "Notice",
  RISK: "Risk",
  BLOCKER: "Blocker",
  DECISION: "Decision",
  LINK: "Link",
};

export function WorkspaceRecordItem({
  access,
  canManage,
  csrfToken,
  onSaved,
  record,
}: WorkspaceMutationProps & { canManage: boolean; record: WorkspaceRecord }) {
  const [archiving, setArchiving] = useState(false);
  const [resolution, setResolution] = useState("");
  const resolve = useMutation({
    mutationFn: () =>
      api.resolveWorkspaceRecord(
        access.teamId,
        record.id,
        {
          expectedVersion: record.version,
          grantId: access.grantId!,
          resolution: resolution.trim(),
        },
        csrfToken,
      ),
    onSuccess: onSaved,
  });
  const link = record.kind === "LINK" && record.url;
  const archiveLabel = record.kind === "LINK" ? "Remove" : "Archive";
  return (
    <li className="workspace-record">
      <header>
        <span>{kindLabels[record.kind]}</span>
        <small>
          {record.createdByDisplayName} · {formatDate(record.updatedAt, true)}
        </small>
      </header>
      <h4>
        {link ? (
          <a href={record.url!} rel="noopener noreferrer" target="_blank">
            {record.title}
          </a>
        ) : (
          record.title
        )}
      </h4>
      <p>{record.body}</p>
      {canManage && !archiving ? (
        <button
          className="button button--quiet workspace-record__action"
          onClick={() => setArchiving(true)}
          type="button"
        >
          {archiveLabel} {record.title}
        </button>
      ) : null}
      {canManage && archiving ? (
        <ArchiveForm
          archiveLabel={archiveLabel}
          error={resolve.isError ? resolve.error : null}
          pending={resolve.isPending}
          resolution={resolution}
          save={() => resolve.mutate()}
          setArchiving={setArchiving}
          setResolution={setResolution}
        />
      ) : null}
    </li>
  );
}

function ArchiveForm({
  archiveLabel,
  error,
  pending,
  resolution,
  save,
  setArchiving,
  setResolution,
}: {
  archiveLabel: string;
  error: Error | null;
  pending: boolean;
  resolution: string;
  save: () => void;
  setArchiving: (value: boolean) => void;
  setResolution: (value: string) => void;
}) {
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        save();
      }}
    >
      <label className="form-field">
        Reason
        <span className="field-hint">
          Required, at least 10 characters. Kept in the workspace record.
        </span>
        <textarea
          maxLength={1000}
          minLength={10}
          onChange={(event) => setResolution(event.target.value)}
          required
          rows={2}
          value={resolution}
        />
      </label>
      {error ? (
        <p className="form-banner form-banner--error" role="alert">
          {workspaceRecordErrorText(error)}
        </p>
      ) : null}
      <div className="workspace-record__actions">
        <button
          className="button button--primary"
          disabled={pending || resolution.trim().length < 10}
          type="submit"
        >
          {pending ? "Saving…" : `Confirm ${archiveLabel.toLowerCase()}`}
        </button>
        <button className="button button--quiet" onClick={() => setArchiving(false)} type="button">
          Keep
        </button>
      </div>
    </form>
  );
}
