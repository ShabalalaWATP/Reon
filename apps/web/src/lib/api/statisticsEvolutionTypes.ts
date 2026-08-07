import type {
  ProjectionFreshness,
  StatisticsRange,
  StatisticsScope,
} from "./statisticsTypes";

export type StatisticsUnit = "count" | "percentage" | "hours";

export type PeriodComparison = {
  key: string;
  label: string;
  current: number | null;
  previous: number | null;
  change: number | null;
  unit: StatisticsUnit;
  suppressed: boolean;
};

export type BottleneckMeasure = {
  key: string;
  label: string;
  activeCount: number | null;
  medianAgeHours: number | null;
  p90AgeHours: number | null;
  overdueCount: number | null;
  suppressed: boolean;
};

export type CapacityMeasure = {
  date: string;
  availableMinutes: number;
  reservedMinutes: number;
  activeWorkMinutes: number;
  projectedDemandMinutes: number;
  estimate: boolean;
};

export type ReleaseMeasure = {
  key: string;
  label: string;
  count: number | null;
  medianHours: number | null;
  suppressed: boolean;
};

export type NotificationMeasure = {
  key: string;
  label: string;
  count: number | null;
  medianResponseHours: number | null;
  unresolvedCount: number | null;
  suppressed: boolean;
};

export type IterationMeasure = {
  key: string;
  label: string;
  committedCount: number | null;
  completedCount: number | null;
  completionPercentage: number | null;
  suppressed: boolean;
};

export type ProjectionPeriod = {
  date: string;
  demandCount: number;
  capacityCount: number;
};

export type ExportPolicy = {
  state: "AVAILABLE" | "DENIED" | "SUPPRESSED" | "PENDING";
  reason: string;
};

export type StatisticsEvolution = {
  scope: StatisticsScope;
  range: StatisticsRange;
  freshness: ProjectionFreshness;
  comparison: PeriodComparison[];
  bottlenecks: BottleneckMeasure[];
  capacity: CapacityMeasure[];
  releases: ReleaseMeasure[];
  notifications: NotificationMeasure[];
  iterations: IterationMeasure[];
  projection: {
    label: string;
    estimate: true;
    periods: ProjectionPeriod[];
  };
  exports: {
    csv: ExportPolicy;
    pdf: ExportPolicy;
  };
};

export type StatisticsEvolutionFilters = {
  scopeId: string;
  from: string;
  to: string;
  timeZone: string;
};

export type StatisticsExportResult = {
  state: "READY" | "PENDING";
  downloadUrl: string | null;
  expiresAt: string | null;
  message: string;
};
