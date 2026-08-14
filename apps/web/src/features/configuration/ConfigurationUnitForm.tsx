import { useEffect, useState, type FormEvent } from "react";

import type {
  CandidateGroupDraft,
  ConfigurationDraftInput,
  ConfigurationUnitDraft,
  ConfigurationVersion,
} from "../../lib/api/configurationTypes";
import { configurationUnitAt, draftFrom, validParentUnits } from "./configurationModel";
import { applyUnitChange, type UnitChange } from "./configurationUnitChanges";

type Operation = "CREATE" | "RENAME" | "MOVE" | "RETIRE" | "MAPPING";

export function ConfigurationUnitForm({
  disabled,
  onSave,
  selectedId,
  version,
}: {
  disabled: boolean;
  onSave: (draft: ConfigurationDraftInput) => void;
  selectedId: string | null;
  version: ConfigurationVersion;
}) {
  const selected = configurationUnitAt(version.units, selectedId, version.effectiveFrom);
  const [operation, setOperation] = useState<Operation>(selected ? "RENAME" : "CREATE");
  useEffect(() => setOperation(selected ? "RENAME" : "CREATE"), [selected]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const draft = draftFrom(version);
    applyUnitChange(draft, changeFromForm(operation, selected, data));
    onSave(draft);
  }

  return (
    <form className="configuration-unit-form" onSubmit={submit}>
      <div className="section-heading">
        <span>Explicit change</span>
        <h3>{selected ? selected.name : "Add organisation unit"}</h3>
      </div>
      <fieldset disabled={disabled}>
        <label className="form-field">
          <span>Change</span>
          <select
            onChange={(event) => setOperation(event.target.value as Operation)}
            value={operation}
          >
            <option value="CREATE">Create unit</option>
            {selected ? (
              <>
                <option value="RENAME">Rename unit</option>
                {selected.kind !== "ROOT" ? <option value="MOVE">Move unit</option> : null}
                <option value="RETIRE">Retire from new routing</option>
                <option value="MAPPING">Candidate groups</option>
              </>
            ) : null}
          </select>
        </label>
        <OperationFields operation={operation} selected={selected} version={version} />
      </fieldset>
      <button className="button button--primary" disabled={disabled} type="submit">
        Save proposed change
      </button>
      <p className="configuration-form-note">
        Referenced units remain in history. Validation checks the complete route before approval.
      </p>
    </form>
  );
}

function OperationFields({
  operation,
  selected,
  version,
}: {
  operation: Operation;
  selected: ConfigurationUnitDraft | null;
  version: ConfigurationVersion;
}) {
  if (operation === "CREATE")
    return (
      <CreateFields
        edges={version.edges}
        effectiveAt={version.effectiveFrom}
        units={version.units}
      />
    );
  if (!selected) return null;
  if (operation === "RENAME")
    return (
      <label className="form-field">
        <span>New display name</span>
        <input defaultValue={selected.name} maxLength={120} name="name" required />
      </label>
    );
  if (operation === "MOVE")
    return (
      <ParentField
        childKind={selected.kind}
        currentId={selected.unitId}
        edges={version.edges}
        effectiveAt={version.effectiveFrom}
        units={version.units}
      />
    );
  if (operation === "RETIRE")
    return (
      <label className="form-field">
        <span>Effective retirement</span>
        <input name="effectiveUntil" required type="datetime-local" />
      </label>
    );
  return (
    <MappingFields
      groups={version.candidateGroups.filter((item) => item.unitId === selected.unitId)}
      kind={selected.kind}
    />
  );
}

function CreateFields({
  edges,
  effectiveAt,
  units,
}: {
  edges: ConfigurationVersion["edges"];
  effectiveAt: string;
  units: ConfigurationUnitDraft[];
}) {
  const [kind, setKind] = useState<Exclude<ConfigurationUnitDraft["kind"], "ROOT">>("COMMAND");
  return (
    <>
      <label className="form-field">
        <span>Stable code</span>
        <input name="code" pattern="[A-Z][A-Z0-9_]{1,39}" required />
      </label>
      <label className="form-field">
        <span>Display name</span>
        <input maxLength={120} name="name" required />
      </label>
      <label className="form-field">
        <span>Unit kind</span>
        <select
          name="kind"
          onChange={(event) => setKind(event.target.value as typeof kind)}
          value={kind}
        >
          <option value="COMMAND">Command</option>
          <option value="OPS_GROUP">Ops group</option>
          <option value="TEAM">Delivery team</option>
        </select>
      </label>
      <ParentField
        childKind={kind}
        edges={edges}
        effectiveAt={effectiveAt}
        key={kind}
        units={units}
      />
      <div className="configuration-inline-fields">
        <label className="form-field">
          <span>Minimum Managers</span>
          <input defaultValue={0} min={0} name="minimumManagers" type="number" />
        </label>
        <label className="form-field">
          <span>Minimum Analysts</span>
          <input defaultValue={0} min={0} name="minimumAnalysts" type="number" />
        </label>
      </div>
    </>
  );
}

function ParentField({
  childKind,
  currentId,
  edges,
  effectiveAt,
  units,
}: {
  childKind: ConfigurationUnitDraft["kind"];
  currentId?: string;
  edges: ConfigurationVersion["edges"];
  effectiveAt: string;
  units: ConfigurationUnitDraft[];
}) {
  const parents = validParentUnits(units, edges, childKind, effectiveAt, currentId);
  return (
    <label className="form-field">
      <span>Parent unit</span>
      <select aria-label="Parent unit" name="parentUnitId" required>
        <option value="">Select parent</option>
        {parents.map((unit) => (
          <option key={unit.unitId} value={unit.unitId}>
            {unit.name} · {unit.code}
          </option>
        ))}
      </select>
      <small>
        {parents.length
          ? `Only valid ${childKind === "COMMAND" ? "root" : childKind === "OPS_GROUP" ? "Command" : "Ops group"} parents are shown.`
          : "No structurally valid parent is available."}
      </small>
    </label>
  );
}

function MappingFields({
  groups,
  kind,
}: {
  groups: CandidateGroupDraft[];
  kind: ConfigurationUnitDraft["kind"];
}) {
  const group = (purpose: CandidateGroupDraft["purpose"]) =>
    groups.find((item) => item.purpose === purpose)?.candidateGroup ?? "";
  return kind === "TEAM" ? (
    <>
      <GroupField defaultValue={group("MANAGER")} label="Manager candidate group" name="manager" />
      <GroupField defaultValue={group("ANALYST")} label="Analyst candidate group" name="analyst" />
    </>
  ) : (
    <GroupField defaultValue={group("ROUTING")} label="Routing candidate group" name="routing" />
  );
}

function GroupField({
  defaultValue,
  label,
  name,
}: {
  defaultValue: string;
  label: string;
  name: string;
}) {
  return (
    <label className="form-field">
      <span>{label}</span>
      <input
        defaultValue={defaultValue}
        name={name}
        pattern="[a-z0-9][a-z0-9-]*[a-z0-9]"
        required
      />
    </label>
  );
}

function changeFromForm(
  operation: Operation,
  selected: ConfigurationUnitDraft | null,
  data: FormData,
): UnitChange {
  if (operation === "CREATE")
    return {
      kind: "CREATE",
      input: {
        code: String(data.get("code")).trim(),
        kind: String(data.get("kind")) as ConfigurationUnitDraft["kind"],
        minimumAnalysts: Number(data.get("minimumAnalysts")),
        minimumManagers: Number(data.get("minimumManagers")),
        name: String(data.get("name")).trim(),
        parentUnitId: String(data.get("parentUnitId")),
      },
    };
  if (!selected) throw new Error("Select an organisation unit before changing it.");
  if (operation === "RENAME")
    return { kind: "RENAME", name: String(data.get("name")).trim(), selected };
  if (operation === "MOVE")
    return { kind: "MOVE", parentUnitId: String(data.get("parentUnitId")), selected };
  if (operation === "RETIRE")
    return { effectiveUntil: iso(data, "effectiveUntil"), kind: "RETIRE", selected };
  return { groups: mappingGroups(selected, data), kind: "MAPPING", selected };
}

function mappingGroups(unit: ConfigurationUnitDraft, data: FormData) {
  const purposes: CandidateGroupDraft["purpose"][] =
    unit.kind === "TEAM" ? ["MANAGER", "ANALYST"] : ["ROUTING"];
  return purposes.map((purpose) => ({
    candidateGroup: String(data.get(purpose.toLowerCase())).trim(),
    purpose,
    unitId: unit.unitId,
  }));
}

function iso(data: FormData, name: string) {
  return new Date(String(data.get(name))).toISOString();
}
