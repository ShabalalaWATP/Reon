import type {
  ConfigurationDraftInput,
  ConfigurationEdgeDraft,
  ConfigurationUnitDraft,
  ConfigurationVersion,
} from "../../lib/api/configurationTypes";

export const configurationStatusLabels = {
  ACTIVE: "Current",
  AWAITING_APPROVAL: "Awaiting approval",
  DRAFT: "Proposed changes",
  REJECTED: "Rejected changes",
  SUPERSEDED: "Previous",
  VALIDATED: "Ready for review",
} as const;

const currentCoreRequestFields = [
  "title",
  "service_category",
  "description",
  "question_to_answer",
  "desired_outcome",
  "background_context",
  "subject_area_or_location",
  "coverage_start",
  "coverage_end",
  "customer_urgency",
  "supported_activity_or_decision",
  "required_by",
  "required_by_reason",
  "preferred_deliverable_type",
  "success_criteria",
  "constraints_or_caveats",
  "supporting_information",
  "sensitivity",
  "handling_instructions",
] as const;

export type ConfigurationTreeRow = ConfigurationUnitDraft & { depth: number };

export function draftFrom(version: ConfigurationVersion): ConfigurationDraftInput {
  return {
    basedOnVersionId: version.basedOnVersionId,
    candidateGroups: version.candidateGroups.map((group) => ({ ...group })),
    edges: version.edges.map((edge) => ({ ...edge })),
    effectiveFrom: version.effectiveFrom,
    label: version.label,
    units: version.units.map((unit) => ({ ...unit })),
    workflowTemplate: {
      ...version.workflowTemplate,
      allowedOutcomes: Object.fromEntries(
        Object.entries(version.workflowTemplate.allowedOutcomes).map(([key, outcomes]) => [key, [...outcomes]]),
      ),
      approvedLinkDomains: [...version.workflowTemplate.approvedLinkDomains],
      artefactTypes: [...version.workflowTemplate.artefactTypes],
      coreFields: [...currentCoreRequestFields],
      productTypes: [...version.workflowTemplate.productTypes],
      reminderDays: [...version.workflowTemplate.reminderDays],
      serviceCategories: [...version.workflowTemplate.serviceCategories],
      taskLabels: { ...version.workflowTemplate.taskLabels },
    },
  };
}

export function configurationRows(
  units: ConfigurationUnitDraft[],
  edges: ConfigurationEdgeDraft[],
  effectiveAt?: string,
) {
  const visibleUnits = effectiveAt ? units.filter((unit) => activeAt(unit, effectiveAt)) : units;
  const visibleEdges = effectiveAt ? edges.filter((edge) => activeAt(edge, effectiveAt)) : edges.filter((edge) => !edge.effectiveUntil);
  const children = new Map<string | null, ConfigurationUnitDraft[]>();
  const parentByChild = new Map(
    visibleEdges.map((edge) => [edge.childUnitId, edge.parentUnitId]),
  );
  for (const unit of visibleUnits) {
    const parent = parentByChild.get(unit.unitId) ?? null;
    children.set(parent, [...(children.get(parent) ?? []), unit]);
  }
  for (const items of children.values()) items.sort((left, right) => left.name.localeCompare(right.name));
  const rows: ConfigurationTreeRow[] = [];
  const seen = new Set<string>();
  const visit = (unit: ConfigurationUnitDraft, depth: number) => {
    if (seen.has(unit.unitId)) return;
    seen.add(unit.unitId);
    rows.push({ ...unit, depth });
    for (const child of children.get(unit.unitId) ?? []) visit(child, depth + 1);
  };
  for (const root of children.get(null) ?? []) visit(root, 0);
  for (const unit of visibleUnits) visit(unit, 0);
  return rows;
}

export function matchesConfigurationRow(row: ConfigurationTreeRow, search: string) {
  const query = search.trim().toLocaleLowerCase();
  if (!query) return true;
  return `${row.name} ${row.code} ${row.kind.replace("_", " ")}`.toLocaleLowerCase().includes(query);
}

export function filterConfigurationRows(
  rows: ConfigurationTreeRow[],
  search: string,
) {
  const query = search.trim().toLocaleLowerCase();
  if (!query) return rows;
  const visible = new Set<string>();
  rows.forEach((row, index) => {
    if (!matchesConfigurationRow(row, query)) return;
    visible.add(row.unitId);
    let expectedDepth = row.depth - 1;
    for (let cursor = index - 1; cursor >= 0 && expectedDepth >= 0; cursor -= 1) {
      if (rows[cursor].depth !== expectedDepth) continue;
      visible.add(rows[cursor].unitId);
      expectedDepth -= 1;
    }
  });
  return rows.filter((row) => visible.has(row.unitId));
}

export function configurationPath(
  units: ConfigurationUnitDraft[],
  edges: ConfigurationEdgeDraft[],
  selectedId: string | null,
  effectiveAt?: string,
) {
  if (!selectedId) return [];
  const visibleUnits = effectiveAt ? units.filter((unit) => activeAt(unit, effectiveAt)) : units;
  const visibleEdges = effectiveAt ? edges.filter((edge) => activeAt(edge, effectiveAt)) : edges.filter((edge) => !edge.effectiveUntil);
  const byId = new Map(visibleUnits.map((unit) => [unit.unitId, unit]));
  const parentByChild = new Map(
    visibleEdges.map((edge) => [edge.childUnitId, edge.parentUnitId]),
  );
  const path: ConfigurationUnitDraft[] = [];
  const seen = new Set<string>();
  let currentId: string | undefined = selectedId;
  while (currentId && !seen.has(currentId)) {
    seen.add(currentId);
    const unit = byId.get(currentId);
    if (!unit) break;
    path.unshift(unit);
    currentId = parentByChild.get(currentId);
  }
  return path;
}

export function configurationUnitAt(
  units: ConfigurationUnitDraft[],
  unitId: string | null,
  effectiveAt: string,
) {
  if (!unitId) return null;
  return units
    .filter((unit) => unit.unitId === unitId && activeAt(unit, effectiveAt))
    .sort((left, right) => Date.parse(right.effectiveFrom) - Date.parse(left.effectiveFrom))[0] ?? null;
}

const parentKind = {
  COMMAND: "ROOT",
  OPS_GROUP: "COMMAND",
  TEAM: "OPS_GROUP",
} as const;

export function validParentUnits(
  units: ConfigurationUnitDraft[],
  edges: ConfigurationEdgeDraft[],
  childKind: ConfigurationUnitDraft["kind"],
  effectiveAt: string,
  currentId?: string,
) {
  if (childKind === "ROOT") return [];
  const requiredKind = parentKind[childKind];
  const currentParent = currentId
    ? edges.find((edge) => edge.childUnitId === currentId && activeAt(edge, effectiveAt))?.parentUnitId
    : undefined;
  return units
    .filter((unit) => {
      return unit.unitId !== currentId && unit.unitId !== currentParent && unit.kind === requiredKind && unit.routingEnabled && activeAt(unit, effectiveAt);
    })
    .sort((left, right) => left.name.localeCompare(right.name));
}

export function activeAt(item: { effectiveFrom: string; effectiveUntil: string | null }, effectiveAt: string) {
  const at = Date.parse(effectiveAt);
  const starts = Date.parse(item.effectiveFrom);
  const ends = item.effectiveUntil ? Date.parse(item.effectiveUntil) : Number.POSITIVE_INFINITY;
  return starts <= at && at < ends;
}

export function localDateTimeValue(date: Date) {
  const localTime = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return localTime.toISOString().slice(0, 16);
}

export function lines(value: FormDataEntryValue | null) {
  return String(value ?? "").split("\n").map((item) => item.trim()).filter(Boolean);
}

export function commaSeparatedNumbers(value: FormDataEntryValue | null) {
  return String(value ?? "")
    .split(",")
    .map((item) => Number(item.trim()))
    .filter((item) => Number.isInteger(item));
}

export function unitState(unit: ConfigurationUnitDraft) {
  if (unit.effectiveUntil) return "Retiring";
  if (!unit.routingEnabled) return "Routing paused";
  if (unit.kind === "TEAM") {
    return `${unit.minimumManagers} Manager · ${unit.minimumAnalysts} Analyst minimum`;
  }
  return "Routing enabled";
}
