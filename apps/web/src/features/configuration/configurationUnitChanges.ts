import type {
  CandidateGroupDraft,
  ConfigurationDraftInput,
  ConfigurationUnitDraft,
} from "../../lib/api/configurationTypes";
import { activeAt } from "./configurationModel";

export type UnitChange =
  | { kind: "CREATE"; input: CreateUnitInput }
  | { kind: "RENAME"; name: string; selected: ConfigurationUnitDraft }
  | { kind: "MOVE"; parentUnitId: string; selected: ConfigurationUnitDraft }
  | { kind: "RETIRE"; effectiveUntil: string; selected: ConfigurationUnitDraft }
  | { groups: CandidateGroupDraft[]; kind: "MAPPING"; selected: ConfigurationUnitDraft };

type CreateUnitInput = {
  code: string;
  kind: ConfigurationUnitDraft["kind"];
  minimumAnalysts: number;
  minimumManagers: number;
  name: string;
  parentUnitId: string;
};

export function applyUnitChange(
  draft: ConfigurationDraftInput,
  change: UnitChange,
  generateId: () => string = crypto.randomUUID,
) {
  if (change.kind === "CREATE") return createUnit(draft, change.input, generateId());
  if (change.kind === "RENAME")
    return replaceUnitRevision(draft, change.selected, { name: change.name });
  if (change.kind === "MOVE") return moveUnit(draft, change.selected.unitId, change.parentUnitId);
  if (change.kind === "RETIRE")
    return retireUnit(draft, change.selected.unitId, change.effectiveUntil);
  replaceMappings(draft, change.selected.unitId, change.groups);
}

function createUnit(draft: ConfigurationDraftInput, input: CreateUnitInput, unitId: string) {
  const team = input.kind === "TEAM";
  draft.units = [
    ...draft.units,
    {
      code: input.code,
      effectiveFrom: draft.effectiveFrom,
      effectiveUntil: null,
      kind: input.kind,
      minimumAnalysts: team ? input.minimumAnalysts : 0,
      minimumManagers: team ? input.minimumManagers : 0,
      name: input.name,
      routingEnabled: true,
      unitId,
    },
  ];
  draft.edges = [
    ...draft.edges,
    {
      childUnitId: unitId,
      effectiveFrom: draft.effectiveFrom,
      effectiveUntil: null,
      parentUnitId: input.parentUnitId,
    },
  ];
}

function replaceUnitRevision(
  draft: ConfigurationDraftInput,
  selected: ConfigurationUnitDraft,
  update: Partial<ConfigurationUnitDraft>,
) {
  const selectedIndex = draft.units.findIndex(
    (unit) => unit.unitId === selected.unitId && unit.effectiveFrom === selected.effectiveFrom,
  );
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
  const nextBoundary =
    draft.edges
      .filter((edge) => edge.childUnitId === unitId)
      .flatMap((edge) => [edge.effectiveFrom, edge.effectiveUntil].filter(isDate))
      .filter((value) => Date.parse(value) > effectiveAt)
      .sort((left, right) => Date.parse(left) - Date.parse(right))[0] ?? null;
  draft.edges = draft.edges.flatMap((edge) =>
    closeActiveEdge(edge, unitId, draft.effectiveFrom, effectiveAt),
  );
  draft.edges.push({
    childUnitId: unitId,
    effectiveFrom: draft.effectiveFrom,
    effectiveUntil: nextBoundary,
    parentUnitId,
  });
}

function closeActiveEdge(
  edge: ConfigurationDraftInput["edges"][number],
  unitId: string,
  effectiveFrom: string,
  effectiveAt: number,
) {
  if (edge.childUnitId !== unitId || !activeAt(edge, effectiveFrom)) return [edge];
  if (Date.parse(edge.effectiveFrom) === effectiveAt) return [];
  return [{ ...edge, effectiveUntil: effectiveFrom }];
}

function retireUnit(draft: ConfigurationDraftInput, unitId: string, effectiveUntil: string) {
  const retirementAt = Date.parse(effectiveUntil);
  draft.units = draft.units.flatMap((unit) =>
    retireRevision(unit, unitId, effectiveUntil, retirementAt),
  );
  draft.edges = draft.edges.flatMap((edge) =>
    retireRevision(edge, unitId, effectiveUntil, retirementAt),
  );
}

function retireRevision<T extends { effectiveFrom: string; effectiveUntil: string | null }>(
  revision: T,
  unitId: string,
  effectiveUntil: string,
  retirementAt: number,
) {
  const revisionUnitId =
    "unitId" in revision
      ? revision.unitId
      : "childUnitId" in revision
        ? revision.childUnitId
        : null;
  if (revisionUnitId !== unitId) return [revision];
  if (Date.parse(revision.effectiveFrom) >= retirementAt) return [];
  if (revision.effectiveUntil && Date.parse(revision.effectiveUntil) <= retirementAt)
    return [revision];
  return [{ ...revision, effectiveUntil }];
}

function replaceMappings(
  draft: ConfigurationDraftInput,
  unitId: string,
  groups: CandidateGroupDraft[],
) {
  draft.candidateGroups = [
    ...draft.candidateGroups.filter((item) => item.unitId !== unitId),
    ...groups,
  ];
}

function isDate(value: string | null): value is string {
  return Boolean(value);
}
