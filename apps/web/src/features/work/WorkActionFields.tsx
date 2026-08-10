import type { ReactNode } from "react";
import type { useForm } from "react-hook-form";

import { localDateInputValue } from "../../lib/dateInputs";
import { EligibleSpecialistField, type SpecialistOptions } from "./EligibleSpecialistField";
import { RoutingDestinationField, type RoutingOptions } from "./RoutingDestinationField";
import type { WorkActionName, WorkActionValues } from "./workActionModel";

type Props = Pick<ReturnType<typeof useForm<WorkActionValues>>, "register"> & {
  action: WorkActionName;
  destinationUnitId?: string;
  errors: ReturnType<typeof useForm<WorkActionValues>>["formState"]["errors"];
  routingOptions: RoutingOptions;
  specialistOptions: SpecialistOptions;
};

export function WorkActionFields({
  action,
  destinationUnitId,
  errors,
  register,
  routingOptions,
  specialistOptions,
}: Props) {
  const error = (name: keyof WorkActionValues) => errors[name]?.message;
  const field = (name: keyof WorkActionValues, label: string, input: ReactNode) => (
    <label className="form-field">
      <span>{label}</span>{input}
      {error(name) ? <small className="field-error" role="alert">{error(name)}</small> : null}
    </label>
  );
  if (reasonActions.has(action)) {
    return field("reason", "Reason", <textarea rows={4} {...register("reason")} />);
  }
  if (action === "resume") {
    return field("note", "Reason for resuming", <textarea rows={3} {...register("note")} />);
  }
  if (action === "progress") {
    return (
      <>
        <RoutingDestinationField error={error("destinationUnitId")} options={routingOptions} register={register} selectedId={destinationUnitId} />
        {field("category", "Confirmed category", <input {...register("category")} />)}
        <label className="form-field">
          <span>Priority</span>
          <select defaultValue="" {...register("priority")}>
            <option disabled value="">Select priority</option>
            <option value="LOW">Low</option><option value="MEDIUM">Medium</option>
            <option value="HIGH">High</option><option value="URGENT">Urgent</option>
          </select>
          {error("priority") ? <small className="field-error" role="alert">{error("priority")}</small> : null}
        </label>
      </>
    );
  }
  if (action === "send_to_allocation" || action === "allocate") {
    return (
      <>
        <RoutingDestinationField error={error("destinationUnitId")} options={routingOptions} register={register} selectedId={destinationUnitId} />
        {action === "send_to_allocation"
          ? field("note", "Routing note", <textarea rows={3} {...register("note")} />)
          : field("requiredCapabilities", "Required capabilities", <textarea placeholder="One capability per line" rows={3} {...register("requiredCapabilities")} />)}
      </>
    );
  }
  if (action === "assign") {
    return <>
      <EligibleSpecialistField error={error("specialistId")} options={specialistOptions} register={register} />
      <label className="form-field">
        <span>Contributors <small className="field-hint">Optional, choose up to 10</small></span>
        <select aria-describedby={error("contributorIds") ? "contributors-error" : undefined} multiple size={Math.min(6, Math.max(3, specialistOptions.items.length))} {...register("contributorIds")}>
          {specialistOptions.items.map((specialist) => <option key={specialist.id} value={specialist.id}>{specialist.displayName}</option>)}
        </select>
        {error("contributorIds") ? <small className="field-error" id="contributors-error" role="alert">{error("contributorIds")}</small> : null}
      </label>
      {field("reason", "Assignment reason", <textarea rows={3} {...register("reason")} />)}
    </>;
  }
  if (action === "submit") {
    return <>{field("deliverableTitle", "Product title", <input {...register("deliverableTitle")} />)}{field("deliverableText", "Product text", <textarea rows={9} {...register("deliverableText")} />)}</>;
  }
  if (action === "request_clarification") {
    return (
      <>
        {field("question", "Question for the Customer", <textarea rows={4} {...register("question")} />)}
        {field("reason", "Why this information is needed", <textarea rows={4} {...register("reason")} />)}
        {field("responseDeadline", "Response deadline", <input min={localDateInputValue(new Date())} type="date" {...register("responseDeadline")} />)}
      </>
    );
  }
  if (action === "provide_clarification") {
    return (
      <>
        <input type="hidden" {...register("threadId")} />
        <input type="hidden" {...register("expectedVersion", { valueAsNumber: true })} />
        {field("information", "Information for the Analyst", <textarea rows={6} {...register("information")} />)}
        {error("threadId") || error("expectedVersion") ? <p className="form-banner form-banner--error" role="alert">Refresh this request before responding.</p> : null}
      </>
    );
  }
  if (action === "provide_information") {
    return field("information", "Additional information", <textarea rows={6} {...register("information")} />);
  }
  if (action === "release") {
    return field("recipients", "Dissemination recipients", <textarea placeholder="One recipient per line" rows={4} {...register("recipients")} />);
  }
  return null;
}

const reasonActions = new Set<WorkActionName>([
  "request_information",
  "close",
  "withdraw",
  "return_to_triage",
  "hold",
  "return_to_coordination",
  "return_for_reallocation",
  "changes_required",
]);
