import type { FormEvent } from "react";

import type {
  ConfigurationDraftInput,
  ConfigurationVersion,
  WorkflowDefinition,
} from "../../lib/api/configurationTypes";
import { commaSeparatedNumbers, draftFrom, lines } from "./configurationModel";

const managedTypes = ["PDF", "DOCX", "PPTX"] as const;

export function WorkflowTemplateForm({
  definitions,
  disabled,
  onSave,
  version,
}: {
  definitions: WorkflowDefinition[];
  disabled: boolean;
  onSave: (draft: ConfigurationDraftInput) => void;
  version: ConfigurationVersion;
}) {
  const template = version.workflowTemplate;
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const draft = draftFrom(version);
    const taskLabels = Object.fromEntries(
      Object.keys(template.taskLabels).map((key) => [key, String(data.get(`task:${key}`)).trim()]),
    );
    const selectedTypes = data.getAll("artefactTypes") as Array<"PDF" | "DOCX" | "PPTX">;
    draft.workflowTemplate = {
      ...draft.workflowTemplate,
      approvedLinkDomains: unique(lines(data.get("approvedLinkDomains")).map((domain) => domain.toLowerCase().replace(/\.$/, ""))),
      artefactTypes: template.artefactTypes.includes("LEGACY_TEXT") ? ["LEGACY_TEXT", ...selectedTypes] : selectedTypes,
      formVersion: String(data.get("formVersion")).trim(),
      notificationPolicyVersion: String(data.get("notificationPolicyVersion")).trim(),
      organisationRootId: String(data.get("organisationRootId")),
      productTypes: unique(lines(data.get("productTypes"))),
      reminderDays: unique(commaSeparatedNumbers(data.get("reminderDays"))).sort((left, right) => left - right),
      serviceCategories: unique(lines(data.get("serviceCategories"))),
      taskLabels,
      workflowDefinitionId: String(data.get("workflowDefinitionId")),
    };
    onSave(draft);
  }

  return (
    <form className="workflow-template-form" onSubmit={submit}>
      <div className="section-heading"><span>Bounded template</span><h3>Request and workflow policy</h3></div>
      <p className="configuration-form-note">The human route, mandatory core fields and allowed outcomes are fixed. Administrators can only select an approved compatible deployment.</p>
      <fieldset disabled={disabled}>
        <div className="configuration-inline-fields">
          <label className="form-field"><span>Request form identifier</span><input defaultValue={template.formVersion} maxLength={80} name="formVersion" pattern="[a-z0-9][a-z0-9._-]*" required /></label>
          <label className="form-field"><span>Notification policy identifier</span><input defaultValue={template.notificationPolicyVersion} maxLength={80} name="notificationPolicyVersion" pattern="[a-z0-9][a-z0-9._-]*" required /></label>
        </div>
        <label className="form-field"><span>Organisation root</span><select defaultValue={template.organisationRootId} name="organisationRootId" required>{version.units.filter((unit) => unit.kind === "ROOT" && !unit.effectiveUntil).map((unit) => <option key={unit.unitId} value={unit.unitId}>{unit.name}</option>)}</select></label>
        <label className="form-field"><span>Approved workflow deployment</span><select defaultValue={template.workflowDefinitionId} name="workflowDefinitionId" required><option value="">Select an approved deployment</option>{definitions.map((definition) => <option key={definition.id} value={definition.id}>{definition.processId} · revision {definition.processVersion}</option>)}</select></label>
        <div className="configuration-inline-fields">
          <LineField defaultValue={template.serviceCategories} label="Service categories" name="serviceCategories" />
          <LineField defaultValue={template.productTypes} label="Preferred product types" name="productTypes" />
        </div>
        <label className="form-field"><span>Reminder days, comma separated</span><input defaultValue={template.reminderDays.join(", ")} name="reminderDays" required /></label>
        <LineField defaultValue={template.approvedLinkDomains} label="Approved external-link domains" name="approvedLinkDomains" optional />
        <fieldset className="configuration-checks"><legend>Managed artefact types</legend>{managedTypes.map((type) => <label key={type}><input defaultChecked={template.artefactTypes.includes(type)} name="artefactTypes" type="checkbox" value={type} />{type}</label>)}</fieldset>
        <div className="configuration-task-table" role="group" aria-label="Human task labels">
          {Object.entries(template.taskLabels).map(([key, label]) => <label className="form-field" key={key}><span>{humanise(key)}</span><input defaultValue={label} maxLength={120} name={`task:${key}`} required /><small>Outcomes fixed: {template.allowedOutcomes[key]?.join(", ")}</small></label>)}
        </div>
      </fieldset>
      <button className="button button--primary" disabled={disabled || !definitions.length} type="submit">Save proposed workflow settings</button>
      {!definitions.length ? <p className="form-banner form-banner--warning" role="status">No compatible deployed workflow is available.</p> : null}
    </form>
  );
}

function LineField({ defaultValue, label, name, optional = false }: { defaultValue: string[]; label: string; name: string; optional?: boolean }) {
  return <label className="form-field"><span>{label}</span><textarea defaultValue={defaultValue.join("\n")} name={name} required={!optional} rows={4} /></label>;
}

function humanise(value: string) {
  return value.replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());
}

function unique<T>(values: T[]) {
  return [...new Set(values)];
}
