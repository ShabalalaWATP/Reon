import { useEffect, useState, type FormEvent } from "react";

import type {
  CandidateGroupDraft,
  ConfigurationDraftInput,
  ConfigurationUnitDraft,
  ConfigurationVersion,
} from "../../lib/api/configurationTypes";
import { draftFrom } from "./configurationModel";

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
  const selected = version.units.find((unit) => unit.unitId === selectedId) ?? null;
  const [operation, setOperation] = useState<Operation>(selected ? "RENAME" : "CREATE");
  useEffect(() => setOperation(selected ? "RENAME" : "CREATE"), [selected]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const draft = draftFrom(version);
    if (operation === "CREATE") createUnit(draft, data);
    if (selected && operation === "RENAME") {
      replaceUnit(draft, selected.unitId, { name: String(data.get("name")).trim() });
    }
    if (selected && operation === "RETIRE") retireUnit(draft, selected.unitId, iso(data, "effectiveUntil"));
    if (selected && operation === "MOVE") moveUnit(draft, selected.unitId, String(data.get("parentUnitId")));
    if (selected && operation === "MAPPING") replaceMappings(draft, selected, data);
    onSave(draft);
  }

  return (
    <form className="configuration-unit-form" onSubmit={submit}>
      <div className="section-heading">
        <span>Explicit change</span><h3>{selected ? selected.name : "Add organisation unit"}</h3>
      </div>
      <fieldset disabled={disabled}>
        <label className="form-field"><span>Change</span><select onChange={(event) => setOperation(event.target.value as Operation)} value={operation}><option value="CREATE">Create unit</option>{selected ? <><option value="RENAME">Rename unit</option>{selected.kind !== "ROOT" ? <option value="MOVE">Move unit</option> : null}<option value="RETIRE">Retire from new routing</option><option value="MAPPING">Candidate groups</option></> : null}</select></label>
        {operation === "CREATE" ? <CreateFields units={version.units} /> : null}
        {selected && operation === "RENAME" ? <label className="form-field"><span>New display name</span><input defaultValue={selected.name} maxLength={120} name="name" required /></label> : null}
        {selected && operation === "MOVE" ? <ParentField currentId={selected.unitId} units={version.units} /> : null}
        {selected && operation === "RETIRE" ? <label className="form-field"><span>Effective retirement</span><input name="effectiveUntil" required type="datetime-local" /></label> : null}
        {selected && operation === "MAPPING" ? <MappingFields groups={version.candidateGroups.filter((item) => item.unitId === selected.unitId)} kind={selected.kind} /> : null}
      </fieldset>
      <button className="button button--primary" disabled={disabled} type="submit">Save draft change</button>
      <p className="configuration-form-note">Referenced units remain in history. Validation checks the complete route before approval.</p>
    </form>
  );
}

function CreateFields({ units }: { units: ConfigurationUnitDraft[] }) {
  return <><label className="form-field"><span>Stable code</span><input name="code" pattern="[A-Z][A-Z0-9_]{1,39}" required /></label><label className="form-field"><span>Display name</span><input maxLength={120} name="name" required /></label><label className="form-field"><span>Unit kind</span><select name="kind"><option value="COMMAND">Command</option><option value="OPS_GROUP">Ops group</option><option value="TEAM">Delivery team</option></select></label><ParentField units={units} /><div className="configuration-inline-fields"><label className="form-field"><span>Minimum Managers</span><input defaultValue={0} min={0} name="minimumManagers" type="number" /></label><label className="form-field"><span>Minimum Analysts</span><input defaultValue={0} min={0} name="minimumAnalysts" type="number" /></label></div></>;
}

function ParentField({ currentId, units }: { currentId?: string; units: ConfigurationUnitDraft[] }) {
  return <label className="form-field"><span>Parent unit</span><select name="parentUnitId" required><option value="">Select parent</option>{units.filter((unit) => unit.unitId !== currentId && !unit.effectiveUntil).map((unit) => <option key={unit.unitId} value={unit.unitId}>{unit.name}</option>)}</select></label>;
}

function MappingFields({ groups, kind }: { groups: CandidateGroupDraft[]; kind: ConfigurationUnitDraft["kind"] }) {
  const group = (purpose: CandidateGroupDraft["purpose"]) => groups.find((item) => item.purpose === purpose)?.candidateGroup ?? "";
  return kind === "TEAM" ? <><GroupField defaultValue={group("MANAGER")} label="Manager candidate group" name="manager" /><GroupField defaultValue={group("ANALYST")} label="Analyst candidate group" name="analyst" /></> : <GroupField defaultValue={group("ROUTING")} label="Routing candidate group" name="routing" />;
}

function GroupField({ defaultValue, label, name }: { defaultValue: string; label: string; name: string }) {
  return <label className="form-field"><span>{label}</span><input defaultValue={defaultValue} name={name} pattern="[a-z0-9][a-z0-9-]*[a-z0-9]" required /></label>;
}

function createUnit(draft: ConfigurationDraftInput, data: FormData) {
  const unitId = crypto.randomUUID();
  const kind = String(data.get("kind")) as ConfigurationUnitDraft["kind"];
  draft.units = [...draft.units, {
    code: String(data.get("code")).trim(), effectiveFrom: draft.effectiveFrom, effectiveUntil: null,
    kind, minimumAnalysts: kind === "TEAM" ? Number(data.get("minimumAnalysts")) : 0,
    minimumManagers: kind === "TEAM" ? Number(data.get("minimumManagers")) : 0,
    name: String(data.get("name")).trim(), routingEnabled: true, unitId,
  }];
  draft.edges = [...draft.edges, { childUnitId: unitId, effectiveFrom: draft.effectiveFrom, effectiveUntil: null, parentUnitId: String(data.get("parentUnitId")) }];
}

function replaceUnit(draft: ConfigurationDraftInput, unitId: string, update: Partial<ConfigurationUnitDraft>) {
  draft.units = draft.units.map((unit) => unit.unitId === unitId ? { ...unit, ...update } : unit);
}

function moveUnit(draft: ConfigurationDraftInput, unitId: string, parentUnitId: string) {
  draft.edges = draft.edges.map((edge) => edge.childUnitId === unitId && !edge.effectiveUntil ? { ...edge, effectiveUntil: draft.effectiveFrom } : edge);
  draft.edges.push({ childUnitId: unitId, effectiveFrom: draft.effectiveFrom, effectiveUntil: null, parentUnitId });
}

function retireUnit(draft: ConfigurationDraftInput, unitId: string, effectiveUntil: string) {
  replaceUnit(draft, unitId, { effectiveUntil });
  draft.edges = draft.edges.map((edge) => edge.childUnitId === unitId && !edge.effectiveUntil ? { ...edge, effectiveUntil } : edge);
}

function replaceMappings(draft: ConfigurationDraftInput, unit: ConfigurationUnitDraft, data: FormData) {
  const purposes: CandidateGroupDraft["purpose"][] = unit.kind === "TEAM" ? ["MANAGER", "ANALYST"] : ["ROUTING"];
  draft.candidateGroups = draft.candidateGroups.filter((item) => item.unitId !== unit.unitId);
  for (const purpose of purposes) {
    draft.candidateGroups.push({ candidateGroup: String(data.get(purpose.toLowerCase())).trim(), purpose, unitId: unit.unitId });
  }
}

function iso(data: FormData, name: string) {
  return new Date(String(data.get(name))).toISOString();
}
