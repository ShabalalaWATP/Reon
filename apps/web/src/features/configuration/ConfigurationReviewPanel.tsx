import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Eye, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { configurationApi } from "../../lib/api/configurationClient";
import type { ConfigurationPreview, ConfigurationVersion } from "../../lib/api/configurationTypes";
import { isSessionElevated, useAuth } from "../../lib/auth/AuthProvider";
import { formatDate } from "../../lib/status";

type Action = "validate" | "submit" | "approve" | "reject" | "activate";

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
  const { session } = useAuth();
  const [reason, setReason] = useState("");
  const elevated = isSessionElevated(session);
  const independent = session!.user.id !== version.createdByUserId;
  const action = useMutation({
    mutationFn: (name: Action) => runAction(name, version, reason, session!.csrfToken),
    onSuccess: async () => {
      setReason("");
      await onChanged();
    },
  });
  const next = nextActions(version);
  return (
    <aside className="configuration-review" aria-labelledby="configuration-review-title">
      <div className="section-heading"><span>Controlled release</span><h2 id="configuration-review-title">Preview and approval</h2></div>
      <section aria-labelledby="change-preview-title" className="configuration-review__section">
        <h3 id="change-preview-title"><Eye aria-hidden="true" size={17} />Change preview</h3>
        {previewError ? <p className="form-banner form-banner--error" role="alert">The comparison preview could not be loaded.</p> : null}
        {!previewError && !preview ? <p className="product-inline-state">Preparing comparison…</p> : null}
        {preview ? <p className="configuration-snapshot-reference"><strong>Snapshot reference</strong><code>{preview.snapshotDigest}</code></p> : null}
        {preview && !preview.changes.length ? <p className="inline-empty">No changes from the base configuration.</p> : null}
        {preview?.changes.length ? <ol className="configuration-change-list">{preview.changes.map((change, index) => <li key={`${change.unitId}-${change.type}-${index}`}><span>{change.type.replace("_", " ")}</span><strong>{change.code}</strong><time dateTime={change.effectiveAt}>From {formatDate(change.effectiveAt, true)}</time><p>{change.message}</p><button className="text-button" onClick={() => onFocusUnit(change.unitId)} type="button">Show in tree</button></li>)}</ol> : null}
      </section>
      <section aria-labelledby="validation-title" className="configuration-review__section">
        <h3 id="validation-title"><AlertTriangle aria-hidden="true" size={17} />Validation findings</h3>
        {!version.findings.length ? <p className="inline-empty">No validation findings recorded.</p> : <ul className="configuration-findings">{version.findings.map((finding, index) => <li className={`configuration-finding configuration-finding--${finding.severity.toLowerCase()}`} key={`${finding.code}-${finding.path}-${index}`}><strong>{finding.code.replaceAll("_", " ")}</strong><p>{finding.message}</p>{finding.unitId ? <button className="text-button" onClick={() => onFocusUnit(finding.unitId!)} type="button">Show affected unit</button> : <small>{finding.path}</small>}</li>)}</ul>}
      </section>
      {next.some((name) => name !== "validate") ? <label className="form-field"><span>Decision reason</span><textarea maxLength={2000} minLength={10} onChange={(event) => setReason(event.target.value)} rows={4} value={reason} /><small>Required for review and activation, 10 to 2,000 characters.</small></label> : null}
      {!elevated ? <p className="form-banner form-banner--warning" role="status"><ShieldCheck aria-hidden="true" size={16} />Confirm sensitive changes above before acting.</p> : null}
      {!independent && version.status === "AWAITING_APPROVAL" ? <p className="form-banner form-banner--warning" role="status">A different Platform Administrator must approve these changes.</p> : null}
      <div className="configuration-review__actions">{next.map((name) => <button className={name === "reject" ? "button" : "button button--primary"} disabled={!canRun(name, elevated, independent, reason) || action.isPending} key={name} onClick={() => action.mutate(name)} type="button">{action.isPending ? "Recording decision…" : actionLabel(name)}</button>)}</div>
      {action.isError ? <p className="form-banner form-banner--error" role="alert">{action.error.message}</p> : null}
      <ConfigurationHistory version={version} />
    </aside>
  );
}

function nextActions(version: ConfigurationVersion): Action[] {
  if (version.status === "DRAFT") return ["validate"];
  if (version.status === "VALIDATED") return ["submit"];
  if (version.status === "AWAITING_APPROVAL" && !version.approval) return ["approve", "reject"];
  if (version.status === "AWAITING_APPROVAL" && version.approval?.decision === "APPROVED") return ["activate"];
  return [];
}

function canRun(action: Action, elevated: boolean, independent: boolean, reason: string) {
  if (!elevated) return false;
  if ((action === "approve" || action === "reject") && !independent) return false;
  return action === "validate" || reason.trim().length >= 10;
}

function runAction(action: Action, version: ConfigurationVersion, reason: string, csrfToken: string) {
  const base = { expectedVersion: version.version };
  if (action === "validate") return configurationApi.validate(version.id, base, csrfToken);
  const review = { ...base, reason: reason.trim() };
  if (action === "submit") return configurationApi.submit(version.id, review, csrfToken);
  if (action === "approve") return configurationApi.approve(version.id, review, csrfToken);
  if (action === "reject") return configurationApi.reject(version.id, review, csrfToken);
  return configurationApi.activate(version.id, review, csrfToken);
}

function actionLabel(action: Action) {
  const labels: Record<Action, string> = { activate: "Activate approved changes", approve: "Approve proposed changes", reject: "Reject proposed changes", submit: "Submit for independent approval", validate: "Validate complete configuration" };
  return labels[action];
}

function ConfigurationHistory({ version }: { version: ConfigurationVersion }) {
  const events = [
    { at: version.createdAt, label: "Proposed changes created" },
    { at: version.validatedAt, label: "Validation completed" },
    { at: version.submittedAt, label: "Submitted for approval" },
    { at: version.approval?.createdAt ?? null, label: version.approval ? `${version.approval.decision === "APPROVED" ? "Approved" : "Rejected"} by ${version.approval.actorUserId}` : "" },
    { at: version.activatedAt, label: "Activated" },
    { at: version.rejectedAt, label: "Rejected" },
  ].filter((event): event is { at: string; label: string } => Boolean(event.at));
  return <section className="configuration-review__section" aria-labelledby="configuration-history-title"><h3 id="configuration-history-title"><CheckCircle2 aria-hidden="true" size={17} />Change history</h3><ol className="configuration-history">{events.map((event) => <li key={`${event.label}-${event.at}`}><strong>{event.label}</strong><time dateTime={event.at}>{formatDate(event.at, true)}</time></li>)}</ol>{version.reason ? <p className="configuration-reason"><strong>Recorded reason</strong>{version.reason}</p> : null}</section>;
}
