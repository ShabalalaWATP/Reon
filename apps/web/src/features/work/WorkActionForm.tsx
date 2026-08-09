import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, type ChangeEvent } from "react";
import { useForm } from "react-hook-form";

import type { ClarificationThread, WorkAction } from "../../lib/api/types";
import type { SpecialistOptions } from "./EligibleSpecialistField";
import type { RoutingOptions } from "./RoutingDestinationField";
import { WorkActionFields } from "./WorkActionFields";
import {
  actionLabels,
  actionRequiresDestination,
  buildWorkAction,
  workActionSchema,
  type WorkActionName,
  type WorkActionValues,
} from "./workActionModel";

type Props = {
  actions: WorkActionName[];
  clarification?: ClarificationThread;
  disabled: boolean;
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
  onActionChange,
  onSubmit,
  routingOptions = idleRoutingOptions,
  specialistOptions = idleSpecialistOptions,
}: Props) {
  const {
    formState: { errors },
    handleSubmit,
    register,
    reset,
    watch,
  } = useForm<WorkActionValues>({
    defaultValues: {
      action: actions[0],
      expectedVersion: clarification?.version,
      threadId: clarification?.id,
    },
    resolver: zodResolver(workActionSchema),
  });
  useEffect(
    () =>
      reset({
        action: actions[0],
        expectedVersion: clarification?.version,
        threadId: clarification?.id,
      }),
    [actions, clarification?.id, clarification?.version, reset],
  );
  const action = watch("action");
  const destinationUnitId = watch("destinationUnitId");
  const actionField = register("action");

  if (actions.length === 0) {
    return <p className="inline-empty">No actions are available for this item.</p>;
  }

  const handleActionChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const nextAction = event.currentTarget.value as WorkActionName;
    void actionField.onChange(event);
    onActionChange?.(nextAction);
  };
  const assignmentUnavailable =
    action === "assign" &&
    (specialistOptions.status !== "ready" || specialistOptions.items.length === 0);
  const routingUnavailable =
    actionRequiresDestination(action) &&
    (routingOptions.status !== "ready" || routingOptions.items.length === 0);
  const clarificationUnavailable =
    action === "provide_clarification" && !clarification;

  return (
    <form
      className="work-action-form"
      noValidate
      onSubmit={(event) =>
        void handleSubmit((values) => onSubmit(buildWorkAction(values)))(event)
      }
    >
      <label className="form-field">
        <span>Outcome</span>
        <select {...actionField} onChange={handleActionChange}>
          {actions.map((name) => (
            <option key={name} value={name}>
              {actionLabels[name]}
            </option>
          ))}
        </select>
      </label>
      <WorkActionFields
        action={action}
        destinationUnitId={destinationUnitId}
        errors={errors}
        register={register}
        routingOptions={routingOptions}
        specialistOptions={specialistOptions}
      />
      <button
        className="button button--primary"
        disabled={disabled || assignmentUnavailable || routingUnavailable || clarificationUnavailable}
        type="submit"
      >
        {disabled ? "Recording outcome…" : actionLabels[action]}
      </button>
      <p className="action-assurance">
        This records a named human decision and advances only the selected workflow outcome.
      </p>
    </form>
  );
}
