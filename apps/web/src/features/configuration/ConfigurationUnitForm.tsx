import { useEffect, useState, type FormEvent } from "react";

import type {
  CandidateGroupDraft,
  ConfigurationDraftInput,
  ConfigurationUnitDraft,
  ConfigurationVersion,
} from "../../lib/api/configurationTypes";
import { activeAt, configurationUnitAt, draftFrom, validParentUnits } from "./configurationModel";

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
    if (operation === "CREATE") createUnit(draft, data);
    if (selected && operation === "RENAME") {
      replaceUnitRevision(draft, selected, { name: String(data.get("name")).trim() });
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
        {operation === "CREATE" ? <CreateFields edges={version.edges} effectiveAt={version.effectiveFrom} units={version.units} /> : null}
        {selected && operation === "RENAME" ? <label className="form-field"><span>New display name</span><input defaultValue={selected.name} maxLength={120} name="name" required /></label> : null}
        {selected && operation === "MOVE" ? <ParentField childKind={selected.kind} currentId={selected.unitId} edges={version.edges} effectiveAt={version.effectiveFrom} units={version.units} /> : null}
        {selected && operation === "RETIRE" ? <label className="form-field"><span>Effective retirement</span><input name="effectiveUntil" required type="datetime-local" /></label> : null}
        {selected && operation === "MAPPING" ? <MappingFields groups={version.candidateGroups.filter((item) => item.unitId === selected.unitId)} kind={selected.kind} /> : null}
      </fieldset>
      <button className="button button--primary" disabled={disabled} type="submit">Save proposed change</button>
      <p className="configuration-form-note">Referenced units remain in history. Validation checks the complete route before approval.</p>
    </form>
  );
}

function CreateFields({ edges, effectiveAt, units }: { edges: ConfigurationVersion["edges"]; effectiveAt: string; units: ConfigurationUnitDraft[] }) {
  const [kind, setKind] = useState<Exclude<ConfigurationUnitDraft["kind"], "ROOT">>("COMMAND");
  return <><label className="form-field"><span>Stable code</span><input name="code" pattern="[A-Z][A-Z0-9_]{1,39}" required /></label><label className="form-field"><span>Display name</span><input maxLength={120} name="name" required /></label><label className="form-field"><span>Unit kind</span><select name="kind" onChange={(event) => setKind(event.target.value as typeof kind)} value={kind}><option value="COMMAND">Command</option><option value="OPS_GROUP">Ops group</option><option value="TEAM">Delivery team</option></select></label><ParentField childKind={kind} edges={edges} effectiveAt={effectiveAt} key={kind} units={units} /><div className="configuration-inline-fields"><label className="form-field"><span>Minimum Managers</span><input defaultValue={0} min={0} name="minimumManagers" type="number" /></label><label className="form-field"><span>Minimum Analysts</span><input defaultValue={0} min={0} name="minimumAnalysts" type="number" /></label></div></>;
}

function ParentField({ childKind, currentId, edges, effectiveAt, units }: { childKind: ConfigurationUnitDraft["kind"]; currentId?: string; edges: ConfigurationVersion["edges"]; effectiveAt: string; units: ConfigurationUnitDraft[] }) {
  const parents = validParentUnits(units, edges, childKind, effectiveAt, currentId);
  return <label className="form-field"><span>Parent unit</span><select aria-label="Parent unit" name="parentUnitId" required><option value="">Select parent</option>{parents.map((unit) => <option key={unit.unitId} value={unit.unitId}>{unit.name} · {unit.code}</option>)}</select><small>{parents.length ? `Only valid ${childKind === "COMMAND" ? "root" : childKind === "OPS_GROUP" ? "Command" : "Ops group"} parents are shown.` : "No structurally valid parent is available."}</small></label>;
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

function replaceUnitRevision(draft: ConfigurationDraftInput, selected: ConfigurationUnitDraft, update: Partial<ConfigurationUnitDraft>) {
  const selectedIndex = draft.units.findIndex((unit) => unit.unitId === selected.unitId && unit.effectiveFrom === selected.effectiveFrom);
  if (selectedIndex < 0) return;
  const current = draft.units[selectedIndex];
  if (current.effectiveFrom === draft.effectiveFrom) {
    draft.units[selectedIndex] = { ...current, ...update };
    return;
  }
  draft.units[selectedIndex] = { ...current, effectiveUntil: draft.effectiveFrom };
  draft.units.push({ ...current, ...update, effectiveFrom: draft.effectiveFrom });
}

function moveUnit(draft: ConfigurationDraftInput, unitId: string, parentUnitId: string) {
  const effectiveAt = Date.parse(draft.effectiveFrom);
  const nextBoundary = draft.edges
    .filter((edge) => edge.childUnitId === unitId)
    .flatMap((edge) => [edge.effectiveFrom, edge.effectiveUntil].filter((value): value is string => Boolean(value)))
    .filter((value) => Date.parse(value) > effectiveAt)
    .sort((left, right) => Date.parse(left) - Date.parse(right))[0] ?? null;
  draft.edges = draft.edges.flatMap((edge) => {
    if (edge.childUnitId !== unitId || !activeAt(edge, draft.effectiveFrom)) return [edge];
    if (Date.parse(edge.effectiveFrom) === effectiveAt) return [];
    return [{ ...edge, effectiveUntil: draft.effectiveFrom }];
  });
  draft.edges.push({ childUnitId: unitId, effectiveFrom: draft.effectiveFrom, effectiveUntil: nextBoundary, parentUnitId });
}

function retireUnit(draft: ConfigurationDraftInput, unitId: string, effectiveUntil: string) {
  const retirementAt = Date.parse(effectiveUntil);
  draft.units = draft.units.flatMap((unit) => {
    if (unit.unitId !== unitId) return [unit];
    if (Date.parse(unit.effectiveFrom) >= retirementAt) return [];
    if (unit.effectiveUntil && Date.parse(unit.effectiveUntil) <= retirementAt) return [unit];
    return [{ ...unit, effectiveUntil }];
  });
  draft.edges = draft.edges.flatMap((edge) => {
    if (edge.childUnitId !== unitId) return [edge];
    if (Date.parse(edge.effectiveFrom) >= retirementAt) return [];
    if (edge.effectiveUntil && Date.parse(edge.effectiveUntil) <= retirementAt) return [edge];
    return [{ ...edge, effectiveUntil }];
  });
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
