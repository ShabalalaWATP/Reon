export type PlanningFreshness = {
  health: "READY" | "STALE" | "REBUILDING";
  label: string;
  sourceVersion: number;
};

export type PlanningSummary = {
  backlogCount: number;
  activeIterationCount: number;
  dueRiskCount: number;
  wipCount: number;
  blockedCount: number;
  availableMinutes: number;
  reservedMinutes: number;
};

export type PlanningLaneItem = {
  id: string;
  kind: "REQUEST" | "PACKAGE";
  reference: string;
  title: string;
  ownerDisplayName: string | null;
  priority: string;
  dueOn: string;
  status: string;
  iterationName: string | null;
  blockerAgeDays: number | null;
  dependencyWarningCount: number;
};

export type PlanningLane = {
  key: string;
  label: string;
  items: PlanningLaneItem[];
};

export type BlockerWarning = {
  packageId: string;
  reference: string;
  title: string;
  ageDays: number;
  reason: string;
};

export type DependencyWarning = {
  packageId: string;
  reference: string;
  title: string;
  dependencyReference: string;
  status: "CLEAR" | "AT_RISK" | "BLOCKED" | "MISSING";
  warning: string;
};

export type IterationProjection = {
  id: string;
  name: string;
  goal: string;
  startsOn: string;
  endsOn: string;
  status: string;
  committedPoints: number;
  completedPoints: number;
  committedPackages: number;
  completedPackages: number;
  factualSummary: string | null;
};

export type ChecklistItem = {
  id: string;
  label: string;
  required: boolean;
  completed: boolean;
};

export type PackageChecklist = {
  packageId: string;
  packageTitle: string;
  templateName: string;
  completedCount: number;
  totalCount: number;
  items: ChecklistItem[];
};

export type PlanningCockpit = {
  teamId: string;
  generatedAt: string;
  advisoryOnly: true;
  freshness: PlanningFreshness;
  summary: PlanningSummary;
  lanes: PlanningLane[];
  blockers: BlockerWarning[];
  dependencies: DependencyWarning[];
  iteration: IterationProjection | null;
  checklists: PackageChecklist[];
};

export type PackageTemplate = {
  id: string;
  name: string;
  description: string;
  version: number;
  checklist: Array<Omit<ChecklistItem, "completed">>;
};

export type CapacityScenarioSummary = {
  id: string;
  name: string;
  version: number;
  startsOn: string;
  endsOn: string;
  status: "DRAFT" | "PREVIEWED" | "COMMITTED";
  updatedAt: string;
};

export type CapacityBreakdown = {
  availableMinutes: number;
  reservedMinutes: number;
  requestWorkMinutes: number;
  packageMinutes: number;
  netMinutes: number;
};

export type CapacityScenarioPreview = {
  token: string;
  expiresAt: string;
  sourceVersion: number;
  baseline: CapacityBreakdown;
  scenario: CapacityBreakdown;
  conflicts: Array<{
    date: string;
    kind: "CAPACITY" | "CALENDAR" | "RESERVATION" | "DEPENDENCY";
    summary: string;
  }>;
  estimateLabel: string;
};

export type CapacityScenarioInput = {
  grantId: string;
  name: string;
  startsOn: string;
  endsOn: string;
  plannedMinutes: number;
  expectedSourceVersion: number;
};
