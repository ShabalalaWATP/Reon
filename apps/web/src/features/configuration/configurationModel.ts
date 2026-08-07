import type {
  ConfigurationDraftInput,
  ConfigurationEdgeDraft,
  ConfigurationUnitDraft,
  ConfigurationVersion,
} from "../../lib/api/configurationTypes";

export const configurationStatusLabels = {
  ACTIVE: "Active",
  AWAITING_APPROVAL: "Awaiting approval",
  DRAFT: "Draft",
  REJECTED: "Rejected",
  SUPERSEDED: "Superseded",
  VALIDATED: "Validated",
} as const;

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
      coreFields: [...version.workflowTemplate.coreFields],
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
) {
  const children = new Map<string | null, ConfigurationUnitDraft[]>();
  const parentByChild = new Map(
    edges.filter((edge) => !edge.effectiveUntil).map((edge) => [edge.childUnitId, edge.parentUnitId]),
  );
  for (const unit of units) {
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
  for (const unit of units) visit(unit, 0);
  return rows;
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
