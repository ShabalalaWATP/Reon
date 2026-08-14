import { AlertTriangle, CheckCircle2, Eye, ShieldCheck } from "lucide-react";

import type { ConfigurationPreview, ConfigurationVersion } from "../../lib/api/configurationTypes";
import { formatDate } from "../../lib/status";
import {
  useConfigurationReviewController,
  type ConfigurationReviewAction,
} from "./useConfigurationReviewController";

export function ConfigurationReviewPanel({
  onChanged,
  onFocusUnit,
  preview,
  previewError,
  version,
}: {
  onChanged: () => Promise<unknown>;
  onFocusUnit: (unitId: string) => void;
  preview: ConfigurationPreview | null;
  previewError: boolean;
  version: ConfigurationVersion;
}) {
  const controller = useConfigurationReviewController(version, onChanged);
  return (
    <aside className="configuration-review" aria-labelledby="configuration-review-title">
      <div className="section-heading">
        <span>Controlled release</span>
        <h2 id="configuration-review-title">Preview and approval</h2>
      </div>
      <ChangePreview onFocusUnit={onFocusUnit} preview={preview} previewError={previewError} />
      <ValidationFindings onFocusUnit={onFocusUnit} version={version} />
      <DecisionControls
        canRun={controller.canRun}
        elevated={controller.elevated}
        independent={controller.independent}
        needsReason={controller.needsReason}
        next={controller.next}
        onAction={(name) => controller.action.mutate(name)}
        pending={controller.action.isPending}
        reason={controller.reason}
        setReason={controller.setReason}
        version={version}
      />
      {controller.action.isError ? (
        <p className="form-banner form-banner--error" role="alert">
          {controller.action.error.message}
        </p>
      ) : null}
      <ConfigurationHistory version={version} />
    </aside>
  );
}

function ChangePreview({
  onFocusUnit,
  preview,
  previewError,
}: {
  onFocusUnit: (unitId: string) => void;
  preview: ConfigurationPreview | null;
  previewError: boolean;
}) {
  return (
    <section aria-labelledby="change-preview-title" className="configuration-review__section">
      <h3 id="change-preview-title">
        <Eye aria-hidden="true" size={17} />
        Change preview
      </h3>
      <PreviewContent onFocusUnit={onFocusUnit} preview={preview} previewError={previewError} />
    </section>
  );
}

function PreviewContent({
  onFocusUnit,
  preview,
  previewError,
}: {
  onFocusUnit: (unitId: string) => void;
  preview: ConfigurationPreview | null;
  previewError: boolean;
}) {
  if (previewError)
    return (
      <p className="form-banner form-banner--error" role="alert">
        The comparison preview could not be loaded.
      </p>
    );
  if (!preview) return <p className="product-inline-state">Preparing comparison…</p>;
  return (
    <>
      <p className="configuration-snapshot-reference">
        <strong>Snapshot reference</strong>
        <code>{preview.snapshotDigest}</code>
      </p>
      {preview.changes.length ? (
        <ol className="configuration-change-list">
          {preview.changes.map((change, index) => (
            <li key={`${change.unitId}-${change.type}-${index}`}>
              <span>{change.type.replace("_", " ")}</span>
              <strong>{change.code}</strong>
              <time dateTime={change.effectiveAt}>From {formatDate(change.effectiveAt, true)}</time>
              <p>{change.message}</p>
              <button
                className="text-button"
                onClick={() => onFocusUnit(change.unitId)}
                type="button"
              >
                Show in tree
              </button>
            </li>
          ))}
        </ol>
      ) : (
        <p className="inline-empty">No changes from the base configuration.</p>
      )}
    </>
  );
}

function ValidationFindings({
  onFocusUnit,
  version,
}: {
  onFocusUnit: (unitId: string) => void;
  version: ConfigurationVersion;
}) {
  return (
    <section aria-labelledby="validation-title" className="configuration-review__section">
      <h3 id="validation-title">
        <AlertTriangle aria-hidden="true" size={17} />
        Validation findings
      </h3>
      {version.findings.length ? (
        <ul className="configuration-findings">
          {version.findings.map((finding, index) => (
            <li
              className={`configuration-finding configuration-finding--${finding.severity.toLowerCase()}`}
              key={`${finding.code}-${finding.path}-${index}`}
            >
              <strong>{finding.code.replaceAll("_", " ")}</strong>
              <p>{finding.message}</p>
              <FindingTarget
                onFocusUnit={onFocusUnit}
                path={finding.path}
                unitId={finding.unitId}
              />
            </li>
          ))}
        </ul>
      ) : (
        <p className="inline-empty">No validation findings recorded.</p>
      )}
    </section>
  );
}

function FindingTarget({
  onFocusUnit,
  path,
  unitId,
}: {
  onFocusUnit: (unitId: string) => void;
  path: string;
  unitId: string | null;
}) {
  if (!unitId) return <small>{path}</small>;
  return (
    <button className="text-button" onClick={() => onFocusUnit(unitId)} type="button">
      Show affected unit
    </button>
  );
}

function DecisionControls({
  canRun,
  elevated,
  independent,
  needsReason,
  next,
  onAction,
  pending,
  reason,
  setReason,
  version,
}: {
  canRun: (action: ConfigurationReviewAction) => boolean;
  elevated: boolean;
  independent: boolean;
  needsReason: boolean;
  next: ConfigurationReviewAction[];
  onAction: (action: ConfigurationReviewAction) => void;
  pending: boolean;
  reason: string;
  setReason: (reason: string) => void;
  version: ConfigurationVersion;
}) {
  return (
    <>
      {needsReason ? (
        <label className="form-field">
          <span>Decision reason</span>
          <textarea
            maxLength={2000}
            minLength={10}
            onChange={(event) => setReason(event.target.value)}
            rows={4}
            value={reason}
          />
          <small>Required for review and activation, 10 to 2,000 characters.</small>
        </label>
      ) : null}
      <DecisionWarnings elevated={elevated} independent={independent} version={version} />
      <div className="configuration-review__actions">
        {next.map((name) => (
          <button
            className={name === "reject" ? "button" : "button button--primary"}
            disabled={!canRun(name) || pending}
            key={name}
            onClick={() => onAction(name)}
            type="button"
          >
            {pending ? "Recording decision…" : actionLabel(name)}
          </button>
        ))}
      </div>
    </>
  );
}

function DecisionWarnings({
  elevated,
  independent,
  version,
}: {
  elevated: boolean;
  independent: boolean;
  version: ConfigurationVersion;
}) {
  return (
    <>
      {!elevated ? (
        <p className="form-banner form-banner--warning" role="status">
          <ShieldCheck aria-hidden="true" size={16} />
          Confirm sensitive changes above before acting.
        </p>
      ) : null}
      {!independent && version.status === "AWAITING_APPROVAL" ? (
        <p className="form-banner form-banner--warning" role="status">
          A different Platform Administrator must approve these changes.
        </p>
      ) : null}
    </>
  );
}

function actionLabel(action: ConfigurationReviewAction) {
  const labels: Record<ConfigurationReviewAction, string> = {
    activate: "Activate approved changes",
    approve: "Approve proposed changes",
    reject: "Reject proposed changes",
    submit: "Submit for independent approval",
    validate: "Validate complete configuration",
  };
  return labels[action];
}

function ConfigurationHistory({ version }: { version: ConfigurationVersion }) {
  const events = [
    { at: version.createdAt, label: "Proposed changes created" },
    { at: version.validatedAt, label: "Validation completed" },
    { at: version.submittedAt, label: "Submitted for approval" },
    {
      at: version.approval?.createdAt ?? null,
      label: version.approval
        ? `${version.approval.decision === "APPROVED" ? "Approved" : "Rejected"} by ${version.approval.actorUserId}`
        : "",
    },
    { at: version.activatedAt, label: "Activated" },
    { at: version.rejectedAt, label: "Rejected" },
  ].filter((event): event is { at: string; label: string } => Boolean(event.at));
  return (
    <section
      className="configuration-review__section"
      aria-labelledby="configuration-history-title"
    >
      <h3 id="configuration-history-title">
        <CheckCircle2 aria-hidden="true" size={17} />
        Change history
      </h3>
      <ol className="configuration-history">
        {events.map((event) => (
          <li key={`${event.label}-${event.at}`}>
            <strong>{event.label}</strong>
            <time dateTime={event.at}>{formatDate(event.at, true)}</time>
          </li>
        ))}
      </ol>
      {version.reason ? (
        <p className="configuration-reason">
          <strong>Recorded reason</strong>
          {version.reason}
        </p>
      ) : null}
    </section>
  );
}
