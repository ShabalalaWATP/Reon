import type { WorkPackage, WorkPackageInput, WorkPackagePriority } from "../../lib/api/boardTypes";

export type WorkPackageFormValue = {
  title: string;
  description: string;
  ownerUserId: string;
  contributorIds: string[];
  estimatePoints: number;
  remainingEffortMinutes: number;
  dueOn: string;
  priority: WorkPackagePriority;
  blockers: string;
  acceptanceCriteria: string;
  linkedRequestId: string;
  dependencyIds: string[];
  iterationId: string;
};

export function emptyWorkPackage(ownerUserId: string): WorkPackageFormValue {
  return {
    title: "",
    description: "",
    ownerUserId,
    contributorIds: [],
    estimatePoints: 3,
    remainingEffortMinutes: 120,
    dueOn: "",
    priority: "MEDIUM",
    blockers: "",
    acceptanceCriteria: "",
    linkedRequestId: "",
    dependencyIds: [],
    iterationId: "",
  };
}

export function workPackageValue(item: WorkPackage): WorkPackageFormValue {
  return {
    title: item.title,
    description: item.description,
    ownerUserId: item.ownerUserId,
    contributorIds: item.contributors.map((contributor) => contributor.userId),
    estimatePoints: item.estimatePoints,
    remainingEffortMinutes: item.remainingEffortMinutes,
    dueOn: item.dueOn,
    priority: item.priority,
    blockers: item.blockers,
    acceptanceCriteria: item.acceptanceCriteria,
    linkedRequestId: item.linkedRequestId ?? "",
    dependencyIds: item.dependencyIds,
    iterationId: item.iterationId ?? "",
  };
}

export function workPackageInput(
  value: WorkPackageFormValue,
  grantId: string | null,
): WorkPackageInput {
  return {
    grantId,
    ...value,
    linkedRequestId: value.linkedRequestId || null,
    iterationId: value.iterationId || null,
  };
}
