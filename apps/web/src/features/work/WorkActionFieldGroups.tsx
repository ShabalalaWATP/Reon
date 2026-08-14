import type { ReactNode } from "react";
import type { FieldErrors, UseFormRegister } from "react-hook-form";

import { localDateInputValue } from "../../lib/dateInputs";
import { ContributorPicker } from "./ContributorPicker";
import { EligibleSpecialistField, type SpecialistOptions } from "./EligibleSpecialistField";
import { RoutingDestinationField, type RoutingOptions } from "./RoutingDestinationField";
import type { WorkActionValues } from "./workActionModel";

export type WorkActionFieldGroupProps = {
  contributorIds: string[];
  destinationUnitId?: string;
  errors: FieldErrors<WorkActionValues>;
  managedProducts: boolean;
  register: UseFormRegister<WorkActionValues>;
  routingOptions: RoutingOptions;
  specialistId?: string;
  specialistOptions: SpecialistOptions;
};

type FieldProps = Pick<WorkActionFieldGroupProps, "errors" | "register"> & {
  children: ReactNode;
  label: string;
  name: keyof WorkActionValues;
};

function ActionField({ children, errors, label, name }: FieldProps) {
  const message = errors[name]?.message;
  return (
    <label className="form-field">
      <span>{label}</span>
      {children}
      {message ? (
        <small className="field-error" role="alert">
          {message}
        </small>
      ) : null}
    </label>
  );
}

export function ReasonFields({ errors, register }: WorkActionFieldGroupProps) {
  return (
    <ActionField errors={errors} label="Reason" name="reason" register={register}>
      <textarea rows={4} {...register("reason")} />
    </ActionField>
  );
}

export function ResumeFields({ errors, register }: WorkActionFieldGroupProps) {
  return (
    <ActionField errors={errors} label="Reason for resuming" name="note" register={register}>
      <textarea rows={3} {...register("note")} />
    </ActionField>
  );
}

export function ProgressFields(props: WorkActionFieldGroupProps) {
  const { destinationUnitId, errors, register, routingOptions } = props;
  return (
    <>
      <RoutingDestinationField
        error={errors.destinationUnitId?.message}
        options={routingOptions}
        register={register}
        selectedId={destinationUnitId}
      />
      <ActionField errors={errors} label="Priority" name="priority" register={register}>
        <select defaultValue="" {...register("priority")}>
          <option disabled value="">
            Select priority
          </option>
          <option value="LOW">Low</option>
          <option value="MEDIUM">Medium</option>
          <option value="HIGH">High</option>
          <option value="URGENT">Urgent</option>
        </select>
      </ActionField>
    </>
  );
}

function DestinationFields(props: WorkActionFieldGroupProps) {
  return (
    <RoutingDestinationField
      error={props.errors.destinationUnitId?.message}
      options={props.routingOptions}
      register={props.register}
      selectedId={props.destinationUnitId}
    />
  );
}

export function SendToAllocationFields(props: WorkActionFieldGroupProps) {
  return (
    <>
      <DestinationFields {...props} />
      <ActionField errors={props.errors} label="Routing note" name="note" register={props.register}>
        <textarea rows={3} {...props.register("note")} />
      </ActionField>
    </>
  );
}

export function AllocateFields(props: WorkActionFieldGroupProps) {
  return (
    <>
      <DestinationFields {...props} />
      <ActionField
        errors={props.errors}
        label="Required capabilities"
        name="requiredCapabilities"
        register={props.register}
      >
        <textarea
          placeholder="One capability per line"
          rows={3}
          {...props.register("requiredCapabilities")}
        />
      </ActionField>
    </>
  );
}

export function AssignmentFields(props: WorkActionFieldGroupProps) {
  return (
    <>
      <EligibleSpecialistField
        error={props.errors.specialistId?.message}
        options={props.specialistOptions}
        register={props.register}
      />
      <ContributorPicker
        error={props.errors.contributorIds?.message}
        items={props.specialistOptions.items}
        leadAnalystId={props.specialistId}
        register={props.register}
        selectedIds={props.contributorIds}
      />
      <ActionField
        errors={props.errors}
        label="Assignment reason"
        name="reason"
        register={props.register}
      >
        <textarea rows={3} {...props.register("reason")} />
      </ActionField>
    </>
  );
}

export function SubmitFields(props: WorkActionFieldGroupProps) {
  if (props.managedProducts) {
    return (
      <p className="form-banner" role="status">
        The exact immutable package and Customer covering note shown above will be submitted. No
        legacy text product is required.
      </p>
    );
  }
  return (
    <>
      <ActionField
        errors={props.errors}
        label="Product title"
        name="deliverableTitle"
        register={props.register}
      >
        <input {...props.register("deliverableTitle")} />
      </ActionField>
      <ActionField
        errors={props.errors}
        label="Product text"
        name="deliverableText"
        register={props.register}
      >
        <textarea rows={9} {...props.register("deliverableText")} />
      </ActionField>
    </>
  );
}

export function RequestClarificationFields(props: WorkActionFieldGroupProps) {
  return (
    <>
      <ActionField
        errors={props.errors}
        label="Question for the Customer"
        name="question"
        register={props.register}
      >
        <textarea rows={4} {...props.register("question")} />
      </ActionField>
      <ActionField
        errors={props.errors}
        label="Why this information is needed"
        name="reason"
        register={props.register}
      >
        <textarea rows={4} {...props.register("reason")} />
      </ActionField>
      <ActionField
        errors={props.errors}
        label="Response deadline"
        name="responseDeadline"
        register={props.register}
      >
        <input
          min={localDateInputValue(new Date())}
          type="date"
          {...props.register("responseDeadline")}
        />
      </ActionField>
    </>
  );
}

export function ProvideClarificationFields(props: WorkActionFieldGroupProps) {
  const unavailable = props.errors.threadId || props.errors.expectedVersion;
  return (
    <>
      <input type="hidden" {...props.register("threadId")} />
      <input type="hidden" {...props.register("expectedVersion", { valueAsNumber: true })} />
      <ActionField
        errors={props.errors}
        label="Information for the Analyst"
        name="information"
        register={props.register}
      >
        <textarea rows={6} {...props.register("information")} />
      </ActionField>
      {unavailable ? (
        <p className="form-banner form-banner--error" role="alert">
          Refresh this request before responding.
        </p>
      ) : null}
    </>
  );
}

export function InformationFields(props: WorkActionFieldGroupProps) {
  return (
    <ActionField
      errors={props.errors}
      label="Additional information"
      name="information"
      register={props.register}
    >
      <textarea rows={6} {...props.register("information")} />
    </ActionField>
  );
}

export function ReleaseFields(props: WorkActionFieldGroupProps) {
  if (props.managedProducts) {
    return (
      <p className="form-banner" role="status">
        The originating Customer is derived from the request. Arbitrary release recipients are not
        permitted.
      </p>
    );
  }
  return (
    <ActionField
      errors={props.errors}
      label="Dissemination recipients"
      name="recipients"
      register={props.register}
    >
      <textarea placeholder="One recipient per line" rows={4} {...props.register("recipients")} />
    </ActionField>
  );
}

export function EmptyActionFields() {
  return null;
}
