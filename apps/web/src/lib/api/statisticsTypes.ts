import type { OrganisationUnit } from "./types";

export type StatisticsScope = {
  id: string;
  unitId: string | null;
  name: string;
  kind: OrganisationUnit["kind"] | "PLATFORM";
  includeDescendants: boolean;
};

export type StatisticsRange = {
  fromDate: string;
  toDate: string;
  timeZone: string;
  asOfDate: string;
};

export type ProjectionFreshness = {
  health: "READY" | "REBUILDING" | "DEGRADED";
  lastProjectedAt: string | null;
  sourceEventCount: number;
  projectedRequestCount: number;
};

export type SummaryMetric = {
  key: string;
  label: string;
  value: number | null;
  unit: "count" | "percentage" | "rating" | "hours";
  suppressed: boolean;
};

export type CategoryCount = {
  key: string;
  label: string;
  count: number;
};

export type DailyThroughput = {
  date: string;
  received: number;
  completed: number;
};

export type StageDuration = {
  key: string;
  label: string;
  completedIntervals: number;
  medianHours: number;
  p90Hours: number;
};

export type ChildUnitComparison = {
  unitId: string;
  name: string;
  kind: OrganisationUnit["kind"];
  received: number;
  active: number;
  completed: number;
  overdue: number;
  feedbackCount: number;
  averageRating: number | null;
  ratingSuppressed: boolean;
};

export type MetricDefinition = {
  key: string;
  label: string;
  description: string;
};

export type StatisticsDashboard = {
  scope: StatisticsScope;
  range: StatisticsRange;
  freshness: ProjectionFreshness;
  definitions: MetricDefinition[];
  summary: SummaryMetric[];
  status: CategoryCount[];
  age: CategoryCount[];
  dueRisk: CategoryCount[];
  throughput: DailyThroughput[];
  stageDurations: StageDuration[];
  children: ChildUnitComparison[];
};

export type StatisticsScopeList = { items: StatisticsScope[] };
