import type { ClarificationThread, WorkAction } from "../../lib/api/types";
import type { SpecialistOptions } from "./EligibleSpecialistField";
import type { RoutingOptions } from "./RoutingDestinationField";
import { useWorkActionForm } from "./useWorkActionForm";
import { WorkActionFields } from "./WorkActionFields";
import { actionLabels, type WorkActionName } from "./workActionModel";

type Props = {
  actions: WorkActionName[];
  clarification?: ClarificationThread;
  disabled: boolean;
  managedProducts?: boolean;
  onActionChange?: (action: WorkActionName) => void;
  onSubmit: (action: WorkAction) => void;
  routingOptions?: RoutingOptions;
  specialistOptions?: SpecialistOptions;
};

const idleSpecialistOptions: SpecialistOptions = {
  items: [],
  onRetry: () => undefined,
  status: "idle",
};
const idleRoutingOptions: RoutingOptions = {
  items: [],
  onRetry: () => undefined,
  status: "idle",
};

export function WorkActionForm({
  actions,
  clarification,
  disabled,
  managedProducts = false,
  onActionChange,
  onSubmit,
  routingOptions = idleRoutingOptions,
  specialistOptions = idleSpecialistOptions,
}: Props) {
  const controller = useWorkActionForm({
    actions,
    clarification,
    managedProducts,
    onActionChange,
    onSubmit,
    routingOptions,
    specialistOptions,
  });
  if (actions.length === 0) {
    return <p className="inline-empty">No actions are available for this item.</p>;
  }

  return (
    <form
      className="work-action-form"
      noValidate
      onSubmit={(event) => void controller.submit(event)}
    >
      <label className="form-field">
        <span>Outcome</span>
        <select {...controller.actionField} onChange={controller.changeAction}>
          {actions.map((name) => (
            <option key={name} value={name}>
              {actionLabels[name]}
            </option>
          ))}
        </select>
      </label>
      <WorkActionFields
        action={controller.action}
        contributorIds={controller.contributorIds}
        destinationUnitId={controller.destinationUnitId}
        errors={controller.errors}
        managedProducts={managedProducts}
        register={controller.register}
        routingOptions={routingOptions}
        specialistId={controller.specialistId}
        specialistOptions={specialistOptions}
      />
      <button
        className="button button--primary"
        disabled={disabled || controller.unavailable}
        type="submit"
      >
        {disabled ? "Recording outcome…" : actionLabels[controller.action]}
      </button>
      <p className="action-assurance">
        This records a named human decision and advances only the selected workflow outcome.
      </p>
    </form>
  );
}
