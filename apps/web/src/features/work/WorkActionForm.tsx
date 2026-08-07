import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, type ChangeEvent, type ReactNode } from "react";
import { useForm } from "react-hook-form";

import type { ClarificationThread, WorkAction } from "../../lib/api/types";
import {
  EligibleSpecialistField,
  type SpecialistOptions,
} from "./EligibleSpecialistField";
import {
  RoutingDestinationField,
  type RoutingOptions,
} from "./RoutingDestinationField";
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
      <ActionFields
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

type FieldProps = Pick<ReturnType<typeof useForm<WorkActionValues>>, "register"> & {
  action: WorkActionName;
  destinationUnitId?: string;
  errors: ReturnType<typeof useForm<WorkActionValues>>["formState"]["errors"];
  routingOptions: RoutingOptions;
  specialistOptions: SpecialistOptions;
};

function ActionFields({
  action,
  destinationUnitId,
  errors,
  register,
  routingOptions,
  specialistOptions,
}: FieldProps) {
  const error = (name: keyof WorkActionValues) => errors[name]?.message;
  const field = (name: keyof WorkActionValues, label: string, input: ReactNode) => (
    <label className="form-field">
      <span>{label}</span>
      {input}
      {error(name) ? (
        <small className="field-error" role="alert">
          {error(name)}
        </small>
      ) : null}
    </label>
  );

  if (
    [
      "request_information",
      "close",
      "withdraw",
      "return_to_triage",
      "hold",
      "return_to_coordination",
      "return_for_reallocation",
      "changes_required",
    ].includes(action)
  ) {
    return field("reason", "Reason", <textarea rows={4} {...register("reason")} />);
  }
  if (action === "resume") {
    return field(
      "note",
      "Reason for resuming",
      <textarea rows={3} {...register("note")} />,
    );
  }
  if (action === "progress") {
    return (
      <>
        <RoutingDestinationField
          error={error("destinationUnitId")}
          options={routingOptions}
          register={register}
          selectedId={destinationUnitId}
        />
        <label className="form-field">
          <span>Confirmed category</span>
          <input {...register("category")} />
          {error("category") ? (
            <small className="field-error" role="alert">
              {error("category")}
            </small>
          ) : null}
        </label>
        <label className="form-field">
          <span>Priority</span>
          <select defaultValue="" {...register("priority")}>
            <option disabled value="">
              Select priority
            </option>
            <option value="LOW">Low</option>
            <option value="MEDIUM">Medium</option>
            <option value="HIGH">High</option>
            <option value="URGENT">Urgent</option>
          </select>
          {error("priority") ? (
            <small className="field-error" role="alert">
              {error("priority")}
            </small>
          ) : null}
        </label>
      </>
    );
  }
  if (action === "send_to_allocation") {
    return (
      <>
        <RoutingDestinationField
          error={error("destinationUnitId")}
          options={routingOptions}
          register={register}
          selectedId={destinationUnitId}
        />
        {field(
          "note",
          "Routing note",
          <textarea rows={3} {...register("note")} />,
        )}
      </>
    );
  }
  if (action === "allocate") {
    return (
      <>
        <RoutingDestinationField
          error={error("destinationUnitId")}
          options={routingOptions}
          register={register}
          selectedId={destinationUnitId}
        />
        {field(
          "requiredCapabilities",
          "Required capabilities",
          <textarea
            placeholder="One capability per line"
            rows={3}
            {...register("requiredCapabilities")}
          />,
        )}
      </>
    );
  }
  if (action === "assign") {
    return (
      <EligibleSpecialistField
        error={error("specialistId")}
        options={specialistOptions}
        register={register}
      />
    );
  }
  if (action === "submit") {
    return (
      <>
        {field("deliverableTitle", "Product title", <input {...register("deliverableTitle")} />)}
        {field(
          "deliverableText",
          "Product text",
          <textarea rows={9} {...register("deliverableText")} />,
        )}
      </>
    );
  }
  if (action === "request_clarification") {
    return (
      <>
        {field(
          "question",
          "Question for the Customer",
          <textarea rows={4} {...register("question")} />,
        )}
        {field(
          "reason",
          "Why this information is needed",
          <textarea rows={4} {...register("reason")} />,
        )}
        {field(
          "responseDeadline",
          "Response deadline",
          <input min={new Date().toISOString().slice(0, 10)} type="date" {...register("responseDeadline")} />,
        )}
      </>
    );
  }
  if (action === "provide_clarification") {
    return (
      <>
        <input type="hidden" {...register("threadId")} />
        <input type="hidden" {...register("expectedVersion", { valueAsNumber: true })} />
        {field(
          "information",
          "Information for the Analyst",
          <textarea rows={6} {...register("information")} />,
        )}
        {error("threadId") || error("expectedVersion") ? (
          <p className="form-banner form-banner--error" role="alert">
            Refresh this request before responding.
          </p>
        ) : null}
      </>
    );
  }
  if (action === "provide_information") {
    return field(
      "information",
      "Additional information",
      <textarea rows={6} {...register("information")} />,
    );
  }
  if (action === "release") {
    return field(
      "recipients",
      "Dissemination recipients",
      <textarea
        placeholder="One recipient per line"
        rows={4}
        {...register("recipients")}
      />,
    );
  }
  return null;
}
