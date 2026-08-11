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
  if (!item.assigneeId) {
    if (!claimAllowed) {
      return <section className="action-panel"><h2>Manager assignment required</h2><p>A Team Manager must assign this request before an Analyst can work on it.</p></section>;
    }
    return <section className="action-panel"><h2>Take ownership</h2><p>Claim this item before recording a decision.</p><button className="button button--primary" disabled={disabled} onClick={onClaim} type="button">{disabled ? "Claiming…" : "Claim work item"}</button></section>;
  }
  if (item.assigneeId !== currentUserId) {
    return <section className="action-panel"><h2>Assigned to {item.assigneeDisplayName ?? "another team member"}</h2><p>This item can only be completed by its current owner.</p></section>;
  }
  return <section className="action-panel"><div className="section-heading"><span>Human decision</span><h2>Record outcome</h2></div><WorkActionForm actions={item.availableActions} clarification={clarification} disabled={disabled} onActionChange={onActionChange} onSubmit={onComplete} routingOptions={routingOptions} specialistOptions={specialistOptions} /></section>;
}
