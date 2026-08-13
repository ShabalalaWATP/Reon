import { ChevronDown } from "lucide-react";
import { useState } from "react";

import type { ClarificationThread, WorkAction, WorkItem } from "../../lib/api/types";
import type { SpecialistOptions } from "./EligibleSpecialistField";
import type { RoutingOptions } from "./RoutingDestinationField";
import { WorkActionForm } from "./WorkActionForm";
import type { WorkActionName } from "./workActionModel";

type Props = {
  claimAllowed?: boolean;
  clarification?: ClarificationThread;
  currentUserId: string;
  disabled: boolean;
  item: WorkItem;
  onActionChange?: (action: WorkActionName) => void;
  onClaim: () => void;
  onComplete: (action: WorkAction) => void;
  routingOptions?: RoutingOptions;
  specialistOptions?: SpecialistOptions;
};

export function WorkActionPanel({
  claimAllowed = true,
  clarification,
  currentUserId,
  disabled,
  item,
  onActionChange,
  onClaim,
  onComplete,
  routingOptions,
  specialistOptions,
}: Props) {
  const [collapsed, setCollapsed] = useState(false);
  const assignedToCurrentUser = item.assignedToCurrentUser || item.assigneeId === currentUserId;
  if (!assignedToCurrentUser && !item.assigneeId) {
    if (!claimAllowed) {
      return <section className="action-panel"><h2>Manager assignment required</h2><p>A Team Manager must assign this request before an Analyst can work on it.</p></section>;
    }
    return <section className="action-panel"><h2>Take ownership</h2><p>Claim this item before recording a decision.</p><button className="button button--primary" disabled={disabled} onClick={onClaim} type="button">{disabled ? "Claiming…" : "Claim work item"}</button></section>;
  }
  if (!assignedToCurrentUser) {
    return <section className="action-panel"><h2>Assigned to {item.assigneeDisplayName ?? "another team member"}</h2><p>This item can only be completed by its current owner.</p></section>;
  }
  const bodyId = `action-panel-body-${item.id}`;
  return (
    <section className="action-panel">
      <div className="action-panel__header">
        <div className="section-heading"><span>Human decision</span><h2>Record outcome</h2></div>
        <button
          aria-controls={bodyId}
          aria-expanded={!collapsed}
          className={collapsed ? "action-panel__toggle action-panel__toggle--collapsed" : "action-panel__toggle"}
          onClick={() => setCollapsed((value) => !value)}
          type="button"
        >
          <ChevronDown aria-hidden="true" size={16} />
          <span className="sr-only">{collapsed ? "Expand the decision panel" : "Collapse the decision panel"}</span>
        </button>
      </div>
      {collapsed ? <p className="action-panel__collapsed-note">Decision panel collapsed. Expand it to record the outcome.</p> : null}
      <div className="action-panel__body" hidden={collapsed} id={bodyId}>
        {clarification ? <ClarificationContext thread={clarification} /> : null}
        <WorkActionForm actions={item.availableActions} clarification={clarification} disabled={disabled} onActionChange={onActionChange} onSubmit={onComplete} routingOptions={routingOptions} specialistOptions={specialistOptions} />
      </div>
    </section>
  );
}

function ClarificationContext({ thread }: { thread: ClarificationThread }) {
  return (
    <aside aria-label="Question from the Analyst" className="action-context">
      <span>Question from {thread.assignedSpecialist.displayName}</span>
      <p className="action-context__question">{thread.question}</p>
      <p className="action-context__reason">{thread.reason}</p>
      <small>
        Response requested by {new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" }).format(new Date(thread.responseDeadline))}
      </small>
    </aside>
  );
}
