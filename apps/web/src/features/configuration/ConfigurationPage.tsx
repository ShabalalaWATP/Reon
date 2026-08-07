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
import { configurationStatusLabels, draftFrom } from "./configurationModel";
import { ConfigurationReviewPanel } from "./ConfigurationReviewPanel";
import { ConfigurationTree } from "./ConfigurationTree";
import { ConfigurationUnitForm } from "./ConfigurationUnitForm";
import { WorkflowTemplateForm } from "./WorkflowTemplateForm";

export function ConfigurationPage() {
  const { configurationId } = useParams();
  const navigate = useNavigate();
  const { session } = useAuth();
  const [selectedUnitId, setSelectedUnitId] = useState<string | null>(null);
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

  if (versions.isPending || (selectedId && version.isPending)) return <PageState kind="loading" title="Loading configuration registry" />;
  if (versions.isError || version.isError) return <PageState action={<button className="button" onClick={() => void Promise.all([versions.refetch(), version.refetch()])}>Try again</button>} kind="error" title="Configuration registry could not be loaded" />;
  if (!selectedId || !version.data) return <PageState kind="empty" title="No configuration versions">An initial configuration must be provisioned before drafts can be created.</PageState>;
  const current = version.data;
  const elevated = isSessionElevated(session);
  const editable = elevated && current.status === "DRAFT";
  const focusUnit = (unitId: string) => {
    setSelectedUnitId(unitId);
    requestAnimationFrame(() => document.getElementById(`configuration-unit-${unitId}`)?.focus());
  };
  return (
    <main className="page-stack configuration-page">
      <header className="detail-heading configuration-heading">
        <div><span>Platform administration</span><h1>Organisation and workflow configuration</h1><p>Draft, compare and activate immutable configuration versions without editing executable workflow.</p></div>
        <label className="form-field configuration-version-picker"><span>Version</span><select onChange={(event) => void navigate(`/admin/configuration/${event.target.value}`)} value={current.id}>{versions.data.items.map((item) => <option key={item.id} value={item.id}>v{item.sequence} · {item.label} · {configurationStatusLabels[item.status]}</option>)}</select></label>
      </header>
      <section className="configuration-version-bar" aria-label="Selected configuration version"><div><span className={`configuration-state configuration-state--${current.status.toLowerCase()}`}>{configurationStatusLabels[current.status]}</span><strong>Version {current.sequence}, record {current.version}</strong></div><dl><div><dt>Effective</dt><dd>{formatDate(current.effectiveFrom, true)}</dd></div><div><dt>Created</dt><dd>{formatDate(current.createdAt, true)}</dd></div></dl></section>
      <StepUpPanel />
      {current.status !== "DRAFT" ? <CreateDraftPanel disabled={!elevated} onCreated={(id) => void navigate(`/admin/configuration/${id}`)} source={current} /> : null}
      {current.status !== "DRAFT" ? <p className="configuration-lock-note"><LockKeyhole aria-hidden="true" size={16} />This version is immutable. Create a draft to propose another change.</p> : null}
      <div className="configuration-workspace">
        <section className="configuration-editor" aria-labelledby="organisation-draft-title">
          <header className="product-section-heading"><div><span>Effective-dated structure</span><h2 id="organisation-draft-title">Organisation draft</h2></div><p><GitCompareArrows aria-hidden="true" size={16} />Select a unit to change it</p></header>
          <div className="configuration-organisation-grid">
            <ConfigurationTree edges={current.edges} onSelect={setSelectedUnitId} selectedId={selectedUnitId} units={current.units} />
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

function CreateDraftPanel({ disabled, onCreated, source }: { disabled: boolean; onCreated: (id: string) => void; source: ConfigurationVersion }) {
  const { session } = useAuth();
  const create = useMutation({
    mutationFn: ({ effectiveFrom, label }: { effectiveFrom: string; label: string }) => {
      const draft = draftFrom(source);
      draft.basedOnVersionId = source.id;
      draft.effectiveFrom = new Date(effectiveFrom).toISOString();
      draft.label = label;
      return configurationApi.create(draft, session!.csrfToken);
    },
    onSuccess: (created) => onCreated(created.id),
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    create.mutate({ effectiveFrom: String(data.get("effectiveFrom")), label: String(data.get("label")).trim() });
  }
  return <details className="configuration-create"><summary><Plus aria-hidden="true" size={16} />Create draft from version {source.sequence}</summary><form onSubmit={submit}><label className="form-field"><span>Draft label</span><input maxLength={120} minLength={3} name="label" required /></label><label className="form-field"><span>Effective from</span><input min={new Date().toISOString().slice(0, 16)} name="effectiveFrom" required type="datetime-local" /></label><button className="button button--primary" disabled={disabled || create.isPending} type="submit">{create.isPending ? "Creating draft…" : "Create immutable draft"}</button>{create.isError ? <p className="form-banner form-banner--error" role="alert">{create.error.message}</p> : null}</form></details>;
}
