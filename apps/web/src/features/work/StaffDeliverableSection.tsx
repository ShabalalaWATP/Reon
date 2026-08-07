import type { Deliverable, WorkStage } from "../../lib/api/types";
import { formatDate } from "../../lib/status";

type Props = {
  deliverable?: Deliverable | null;
  stage: WorkStage;
  state: "loading" | "error" | "ready";
};

const stageLabels: Partial<Record<WorkStage, string>> = {
  LEAD_REVIEW: "Submitted service product",
  QUALITY_REVIEW: "Service product for QC review",
  READY_FOR_RELEASE: "Approved service product",
  REWORK_REQUIRED: "Latest submitted version",
};

function showsStaffDeliverable(stage: WorkStage) {
  return stage in stageLabels;
}

export function StaffDeliverableSection({ deliverable, stage, state }: Props) {
  if (!showsStaffDeliverable(stage)) return null;

  return (
    <section
      aria-labelledby="staff-deliverable-title"
      className="staff-deliverable detail-section"
    >
      <div className="section-heading">
        <span>{stageLabels[stage]}</span>
        <h2 id="staff-deliverable-title">Service product</h2>
      </div>
      {state === "loading" ? (
        <p className="inline-loading" role="status">
          Loading submitted service product…
        </p>
      ) : state === "error" ? (
        <p className="form-banner form-banner--error" role="alert">
          Submitted service product could not be loaded.
        </p>
      ) : deliverable ? (
        <article className="deliverable staff-deliverable__content">
          <h3>{deliverable.title}</h3>
          <p>{deliverable.text}</p>
          <small>
            {deliverable.releasedAt
              ? `Disseminated ${formatDate(deliverable.releasedAt, true)}`
              : "Not yet disseminated"}
          </small>
        </article>
      ) : (
        <p className="inline-empty">
          No submitted service product is available for this stage.
        </p>
      )}
    </section>
  );
}
