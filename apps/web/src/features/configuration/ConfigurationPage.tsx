import { useMutation } from "@tanstack/react-query";
import { GitCompareArrows, LockKeyhole, Plus } from "lucide-react";
import type { FormEvent } from "react";

import { PageState } from "../../components/PageState";
import { StepUpPanel } from "../admin/StepUpPanel";
import { configurationApi } from "../../lib/api/configurationClient";
import type { ConfigurationVersion } from "../../lib/api/configurationTypes";
import { useAuth } from "../../lib/auth/AuthProvider";
import { formatDate } from "../../lib/status";
import { configurationStatusLabels, draftFrom, localDateTimeValue } from "./configurationModel";
import { ConfigurationBreadcrumbs } from "./ConfigurationBreadcrumbs";
import { ConfigurationReviewPanel } from "./ConfigurationReviewPanel";
import { ConfigurationTree } from "./ConfigurationTree";
import { ConfigurationUnitForm } from "./ConfigurationUnitForm";
import { useConfigurationPageController } from "./useConfigurationPageController";
import { WorkflowTemplateForm } from "./WorkflowTemplateForm";

export function ConfigurationPage() {
  const controller = useConfigurationPageController();
  if (isLoading(controller)) return <PageState kind="loading" title="Loading configuration" />;
  if (hasLoadError(controller)) return <ConfigurationLoadError controller={controller} />;
  if (!controller.selectedId || !controller.version.data)
    return (
      <PageState kind="empty" title="No configuration available">
        An initial configuration must be provisioned before changes can be proposed.
      </PageState>
    );
  return <ConfigurationWorkspace controller={controller} current={controller.version.data} />;
}

type Controller = ReturnType<typeof useConfigurationPageController>;

function ConfigurationWorkspace({
  controller,
  current,
}: {
  controller: Controller;
  current: ConfigurationVersion;
}) {
  return (
    <main className="page-stack configuration-page">
      <ConfigurationHeading controller={controller} current={current} />
      <VersionSummary current={current} />
      <StepUpPanel />
      <ImmutableConfigurationActions controller={controller} current={current} />
      <div className="configuration-workspace">
        <ConfigurationEditor controller={controller} current={current} />
        <ConfigurationReviewPanel
          onChanged={controller.refresh}
          onFocusUnit={controller.focusUnit}
          preview={controller.preview.data ?? null}
          previewError={controller.preview.isError}
          version={current}
        />
      </div>
    </main>
  );
}

function ConfigurationHeading({
  controller,
  current,
}: {
  controller: Controller;
  current: ConfigurationVersion;
}) {
  return (
    <header className="detail-heading configuration-heading">
      <div>
        <span>Platform administration</span>
        <h1>Organisation and workflow configuration</h1>
        <p>Prepare, compare and approve controlled changes without editing executable workflow.</p>
      </div>
      <label className="form-field configuration-version-picker">
        <span>Configuration history</span>
        <select
          onChange={(event) =>
            void controller.navigate(`/admin/configuration/${event.target.value}`)
          }
          value={current.id}
        >
          {controller.versions.data!.items.map((item) => (
            <option key={item.id} value={item.id}>
              {item.label} · Ref {item.id.slice(0, 8)} · {configurationStatusLabels[item.status]}
            </option>
          ))}
        </select>
      </label>
    </header>
  );
}

function VersionSummary({ current }: { current: ConfigurationVersion }) {
  return (
    <section className="configuration-version-bar" aria-label="Selected configuration">
      <div>
        <span
          className={`configuration-state configuration-state--${current.status.toLowerCase()}`}
        >
          {configurationStatusLabels[current.status]}
        </span>
        <strong>
          {current.label} · Ref {current.id.slice(0, 8)}
        </strong>
      </div>
      <dl>
        <div>
          <dt>Effective</dt>
          <dd>{formatDate(current.effectiveFrom, true)}</dd>
        </div>
        <div>
          <dt>Created</dt>
          <dd>{formatDate(current.createdAt, true)}</dd>
        </div>
      </dl>
    </section>
  );
}

function ImmutableConfigurationActions({
  controller,
  current,
}: {
  controller: Controller;
  current: ConfigurationVersion;
}) {
  if (current.status === "DRAFT") return null;
  const onCreated = async (id: string) => {
    await controller.versions.refetch();
    void controller.navigate(`/admin/configuration/${id}`);
  };
  return (
    <>
      <CreateProposalPanel disabled={!controller.elevated} onCreated={onCreated} source={current} />
      <p className="configuration-lock-note">
        <LockKeyhole aria-hidden="true" size={16} />
        This configuration is immutable. Create proposed changes to prepare an attributable update.
      </p>
    </>
  );
}

function ConfigurationEditor({
  controller,
  current,
}: {
  controller: Controller;
  current: ConfigurationVersion;
}) {
  return (
    <section className="configuration-editor" aria-labelledby="organisation-structure-title">
      <header className="product-section-heading">
        <div>
          <span>Effective-dated structure</span>
          <h2 id="organisation-structure-title">Organisation structure</h2>
        </div>
        <p>
          <GitCompareArrows aria-hidden="true" size={16} />
          Select a unit to inspect or change it
        </p>
      </header>
      <ConfigurationBreadcrumbs
        edges={current.edges}
        effectiveAt={current.effectiveFrom}
        onSelect={controller.focusUnit}
        selectedId={controller.selectedUnitId}
        units={current.units}
      />
      <div className="configuration-organisation-grid">
        <ConfigurationTree
          edges={current.edges}
          effectiveAt={current.effectiveFrom}
          onSearchChange={controller.setTreeSearch}
          onSelect={controller.setSelectedUnitId}
          search={controller.treeSearch}
          selectedId={controller.selectedUnitId}
          units={current.units}
        />
        <ConfigurationUnitForm
          disabled={!controller.editable || controller.replace.isPending}
          onSave={controller.replace.mutate}
          selectedId={controller.selectedUnitId}
          version={current}
        />
      </div>
      {controller.replace.isError ? (
        <p className="form-banner form-banner--error" role="alert">
          {controller.replace.error.message}
        </p>
      ) : null}
      <WorkflowTemplateForm
        definitions={controller.definitions.data?.items ?? []}
        disabled={
          !controller.editable || controller.replace.isPending || controller.definitions.isError
        }
        onSave={controller.replace.mutate}
        version={current}
      />
      {controller.definitions.isError ? (
        <p className="form-banner form-banner--error" role="alert">
          Approved workflow deployments could not be loaded.
        </p>
      ) : null}
    </section>
  );
}

function isLoading(controller: Controller) {
  return (
    controller.versions.isPending || Boolean(controller.selectedId && controller.version.isPending)
  );
}

function hasLoadError(controller: Controller) {
  return controller.versions.isError || controller.version.isError;
}

function ConfigurationLoadError({ controller }: { controller: Controller }) {
  const retry = () =>
    void Promise.all([controller.versions.refetch(), controller.version.refetch()]);
  return (
    <PageState
      action={
        <button className="button" onClick={retry}>
          Try again
        </button>
      }
      kind="error"
      title="Configuration could not be loaded"
    />
  );
}

function CreateProposalPanel({
  disabled,
  onCreated,
  source,
}: {
  disabled: boolean;
  onCreated: (id: string) => Promise<void>;
  source: ConfigurationVersion;
}) {
  const { session } = useAuth();
  const create = useMutation({
    mutationFn: ({ effectiveFrom, label }: { effectiveFrom: string; label: string }) => {
      const draft = draftFrom(source);
      draft.basedOnVersionId = source.id;
      draft.effectiveFrom = new Date(effectiveFrom).toISOString();
      draft.label = label;
      return configurationApi.create(draft, session!.csrfToken);
    },
    onSuccess: async (created) => {
      await onCreated(created.id);
    },
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    create.mutate({
      effectiveFrom: String(data.get("effectiveFrom")),
      label: String(data.get("label")).trim(),
    });
  }
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  return (
    <details className="configuration-create">
      <summary>
        <Plus aria-hidden="true" size={16} />
        Propose changes from {source.label}
      </summary>
      <form onSubmit={submit}>
        <label className="form-field">
          <span>Change title</span>
          <input maxLength={120} minLength={3} name="label" required />
        </label>
        <label className="form-field">
          <span>Effective from</span>
          <input
            aria-label="Effective from"
            min={localDateTimeValue(new Date())}
            name="effectiveFrom"
            required
            type="datetime-local"
          />
          <small>Entered in {timeZone}; stored as an absolute time.</small>
        </label>
        <button
          className="button button--primary"
          disabled={disabled || create.isPending}
          type="submit"
        >
          {create.isPending ? "Preparing changes…" : "Create proposed changes"}
        </button>
        {create.isError ? (
          <p className="form-banner form-banner--error" role="alert">
            {create.error.message}
          </p>
        ) : null}
      </form>
    </details>
  );
}
