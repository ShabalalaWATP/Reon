import { useMutation, useQuery } from "@tanstack/react-query";
import { GitCompareArrows, LockKeyhole, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router";

import { PageState } from "../../components/PageState";
import { StepUpPanel } from "../admin/StepUpPanel";
import { configurationApi } from "../../lib/api/configurationClient";
import type { ConfigurationDraftInput, ConfigurationVersion } from "../../lib/api/configurationTypes";
import { isSessionElevated, useAuth } from "../../lib/auth/AuthProvider";
import { formatDate } from "../../lib/status";
import { configurationStatusLabels, draftFrom, localDateTimeValue } from "./configurationModel";
import { ConfigurationBreadcrumbs } from "./ConfigurationBreadcrumbs";
import { ConfigurationReviewPanel } from "./ConfigurationReviewPanel";
import { ConfigurationTree } from "./ConfigurationTree";
import { ConfigurationUnitForm } from "./ConfigurationUnitForm";
import { WorkflowTemplateForm } from "./WorkflowTemplateForm";

export function ConfigurationPage() {
  const { configurationId } = useParams();
  const navigate = useNavigate();
  const { session } = useAuth();
  const [selectedUnitId, setSelectedUnitId] = useState<string | null>(null);
  const [treeSearch, setTreeSearch] = useState("");
  const versions = useQuery({ queryFn: configurationApi.versions, queryKey: ["protected", session!.user.id, "configuration-versions"] });
  const selectedId = configurationId ?? versions.data?.items[0]?.id;
  const version = useQuery({ enabled: Boolean(selectedId), queryFn: () => configurationApi.version(selectedId!), queryKey: ["protected", session!.user.id, "configuration-version", selectedId] });
  const definitions = useQuery({ queryFn: configurationApi.workflowDefinitions, queryKey: ["protected", session!.user.id, "workflow-definitions"] });
  const preview = useQuery({ enabled: Boolean(selectedId), queryFn: () => configurationApi.preview(selectedId!), queryKey: ["protected", session!.user.id, "configuration-preview", selectedId, version.data?.version] });
  const replace = useMutation({
    mutationFn: (draft: ConfigurationDraftInput) => configurationApi.replace(selectedId!, { ...draft, expectedVersion: version.data!.version }, session!.csrfToken),
    onSuccess: async () => { await refresh(); },
  });
  const refresh = () => Promise.all([version.refetch(), versions.refetch(), preview.refetch()]);

  if (versions.isPending || (selectedId && version.isPending)) return <PageState kind="loading" title="Loading configuration" />;
  if (versions.isError || version.isError) return <PageState action={<button className="button" onClick={() => void Promise.all([versions.refetch(), version.refetch()])}>Try again</button>} kind="error" title="Configuration could not be loaded" />;
  if (!selectedId || !version.data) return <PageState kind="empty" title="No configuration available">An initial configuration must be provisioned before changes can be proposed.</PageState>;
  const current = version.data;
  const elevated = isSessionElevated(session);
  const editable = elevated && current.status === "DRAFT";
  const focusUnit = (unitId: string) => {
    setTreeSearch("");
    setSelectedUnitId(unitId);
    requestAnimationFrame(() => document.getElementById(`configuration-unit-${unitId}`)?.focus());
  };
  return (
    <main className="page-stack configuration-page">
      <header className="detail-heading configuration-heading">
        <div><span>Platform administration</span><h1>Organisation and workflow configuration</h1><p>Prepare, compare and approve controlled changes without editing executable workflow.</p></div>
        <label className="form-field configuration-version-picker"><span>Configuration history</span><select onChange={(event) => void navigate(`/admin/configuration/${event.target.value}`)} value={current.id}>{versions.data.items.map((item) => <option key={item.id} value={item.id}>{item.label} · Ref {item.id.slice(0, 8)} · {configurationStatusLabels[item.status]}</option>)}</select></label>
      </header>
      <section className="configuration-version-bar" aria-label="Selected configuration"><div><span className={`configuration-state configuration-state--${current.status.toLowerCase()}`}>{configurationStatusLabels[current.status]}</span><strong>{current.label} · Ref {current.id.slice(0, 8)}</strong></div><dl><div><dt>Effective</dt><dd>{formatDate(current.effectiveFrom, true)}</dd></div><div><dt>Created</dt><dd>{formatDate(current.createdAt, true)}</dd></div></dl></section>
      <StepUpPanel />
      {current.status !== "DRAFT" ? <CreateProposalPanel disabled={!elevated} onCreated={async (id) => { await versions.refetch(); navigate(`/admin/configuration/${id}`); }} source={current} /> : null}
      {current.status !== "DRAFT" ? <p className="configuration-lock-note"><LockKeyhole aria-hidden="true" size={16} />This configuration is immutable. Create proposed changes to prepare an attributable update.</p> : null}
      <div className="configuration-workspace">
        <section className="configuration-editor" aria-labelledby="organisation-structure-title">
          <header className="product-section-heading"><div><span>Effective-dated structure</span><h2 id="organisation-structure-title">Organisation structure</h2></div><p><GitCompareArrows aria-hidden="true" size={16} />Select a unit to inspect or change it</p></header>
          <ConfigurationBreadcrumbs edges={current.edges} effectiveAt={current.effectiveFrom} onSelect={focusUnit} selectedId={selectedUnitId} units={current.units} />
          <div className="configuration-organisation-grid">
            <ConfigurationTree edges={current.edges} effectiveAt={current.effectiveFrom} onSearchChange={setTreeSearch} onSelect={setSelectedUnitId} search={treeSearch} selectedId={selectedUnitId} units={current.units} />
            <ConfigurationUnitForm disabled={!editable || replace.isPending} onSave={replace.mutate} selectedId={selectedUnitId} version={current} />
          </div>
          {replace.isError ? <p className="form-banner form-banner--error" role="alert">{replace.error.message}</p> : null}
          <WorkflowTemplateForm definitions={definitions.data?.items ?? []} disabled={!editable || replace.isPending || definitions.isError} onSave={replace.mutate} version={current} />
          {definitions.isError ? <p className="form-banner form-banner--error" role="alert">Approved workflow deployments could not be loaded.</p> : null}
        </section>
        <ConfigurationReviewPanel onChanged={refresh} onFocusUnit={focusUnit} preview={preview.data ?? null} previewError={preview.isError} version={current} />
      </div>
    </main>
  );
}

function CreateProposalPanel({ disabled, onCreated, source }: { disabled: boolean; onCreated: (id: string) => Promise<void>; source: ConfigurationVersion }) {
  const { session } = useAuth();
  const create = useMutation({
    mutationFn: ({ effectiveFrom, label }: { effectiveFrom: string; label: string }) => {
      const draft = draftFrom(source);
      draft.basedOnVersionId = source.id;
      draft.effectiveFrom = new Date(effectiveFrom).toISOString();
      draft.label = label;
      return configurationApi.create(draft, session!.csrfToken);
    },
    onSuccess: async (created) => { await onCreated(created.id); },
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    create.mutate({ effectiveFrom: String(data.get("effectiveFrom")), label: String(data.get("label")).trim() });
  }
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  return <details className="configuration-create"><summary><Plus aria-hidden="true" size={16} />Propose changes from {source.label}</summary><form onSubmit={submit}><label className="form-field"><span>Change title</span><input maxLength={120} minLength={3} name="label" required /></label><label className="form-field"><span>Effective from</span><input aria-label="Effective from" min={localDateTimeValue(new Date())} name="effectiveFrom" required type="datetime-local" /><small>Entered in {timeZone}; stored as an absolute time.</small></label><button className="button button--primary" disabled={disabled || create.isPending} type="submit">{create.isPending ? "Preparing changes…" : "Create proposed changes"}</button>{create.isError ? <p className="form-banner form-banner--error" role="alert">{create.error.message}</p> : null}</form></details>;
}
