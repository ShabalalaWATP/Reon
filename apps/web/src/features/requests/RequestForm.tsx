import { zodResolver } from "@hookform/resolvers/zod";
import { cloneElement, type ReactElement, type ReactNode } from "react";
import { useForm, type FieldErrors } from "react-hook-form";
import { z } from "zod";

import type { RequestCreateInput, RequestDraftInput } from "../../lib/api/types";
import { localDateInputValue } from "../../lib/dateInputs";

const today = () => localDateInputValue(new Date());
const requiredText = (minimum: number, message: string, maximum: number) =>
  z.string().trim().min(minimum, message).max(maximum);

const schema = z.object({
  title: requiredText(3, "Enter a clear request title.", 160),
  serviceCategory: requiredText(2, "Choose a service category.", 80),
  description: requiredText(20, "Describe the need in at least 20 characters.", 5000),
  questionToAnswer: requiredText(10, "State the specific question to answer.", 2000),
  desiredOutcome: requiredText(10, "Describe the desired outcome.", 2000),
  backgroundContext: requiredText(1, "Add the known background and context.", 5000),
  subjectAreaOrLocation: requiredText(2, "Define the subject area or location.", 1000),
  coverageStart: z.string().min(1, "Choose the start of the relevant period."),
  coverageEnd: z.string().min(1, "Choose the end of the relevant period."),
  customerUrgency: z.enum(["ROUTINE", "TIME_SENSITIVE", "IMMEDIATE"]),
  supportedActivityOrDecision: requiredText(5, "Explain the activity or decision this will support.", 2000),
  requiredBy: z.string().min(1, "Choose a required-by date.").refine(
    (value) => value >= today(),
    "The required-by date cannot be in the past.",
  ),
  requiredByReason: requiredText(5, "Explain why this date matters and the impact of delay.", 1000),
  preferredDeliverableType: requiredText(2, "Choose a product type.", 80),
  successCriteria: requiredText(5, "Describe how success will be assessed.", 2000),
  constraintsOrCaveats: requiredText(1, "Add constraints or state that none are known.", 2000),
  supportingInformation: requiredText(1, "Describe supporting material or state that none is available.", 2000),
  sensitivity: z.enum(["STANDARD", "SENSITIVE", "RESTRICTED"]),
  handlingInstructions: requiredText(1, "Add handling instructions, or state that standard handling applies.", 2000),
}).refine((values) => !values.coverageStart || !values.coverageEnd || values.coverageEnd >= values.coverageStart, {
  message: "The end cannot be before the start.",
  path: ["coverageEnd"],
});

type FormValues = z.infer<typeof schema>;
type Props = {
  disabled: boolean;
  draftDisabled?: boolean;
  hasDraft?: boolean;
  initialValues?: RequestDraftInput;
  onDeleteDraft?: () => void;
  onSaveDraft?: (input: RequestDraftInput) => void;
  onSubmit: (input: RequestCreateInput) => void;
};

const fieldLabels: Record<keyof FormValues, string> = {
  title: "Request title",
  serviceCategory: "Service category",
  description: "Description of the need",
  questionToAnswer: "Specific question to answer",
  desiredOutcome: "Desired outcome",
  backgroundContext: "Background and known context",
  subjectAreaOrLocation: "Subject area or location",
  coverageStart: "Relevant period starts",
  coverageEnd: "Relevant period ends",
  customerUrgency: "Customer urgency",
  supportedActivityOrDecision: "Activity, project or decision supported",
  requiredBy: "Latest useful delivery date",
  requiredByReason: "Why this date matters and impact if late",
  preferredDeliverableType: "Preferred product type",
  successCriteria: "Success criteria",
  constraintsOrCaveats: "Constraints or caveats",
  supportingInformation: "Supporting information available",
  sensitivity: "Sensitivity",
  handlingInstructions: "Handling instructions",
};

function defaults(draft?: RequestDraftInput): FormValues {
  return {
    title: draft?.title ?? "",
    serviceCategory: draft?.serviceCategory ?? "",
    description: draft?.description ?? "",
    questionToAnswer: draft?.questionToAnswer ?? "",
    desiredOutcome: draft?.desiredOutcome ?? "",
    backgroundContext: draft?.backgroundContext ?? "",
    subjectAreaOrLocation: draft?.subjectAreaOrLocation ?? "",
    coverageStart: draft?.coverageStart ?? "",
    coverageEnd: draft?.coverageEnd ?? "",
    customerUrgency: draft?.customerUrgency ?? "ROUTINE",
    supportedActivityOrDecision: draft?.supportedActivityOrDecision ?? "",
    requiredBy: draft?.requiredBy ?? "",
    requiredByReason: draft?.requiredByReason ?? "",
    preferredDeliverableType: draft?.preferredDeliverableType ?? "",
    successCriteria: draft?.successCriteria ?? "",
    constraintsOrCaveats: draft?.constraintsOrCaveats ?? "",
    supportingInformation: draft?.supportingInformation ?? "",
    sensitivity: draft?.sensitivity ?? "STANDARD",
    handlingInstructions: draft?.handlingInstructions ?? "",
  };
}

export function RequestForm(props: Props) {
  const { formState: { errors, isValid }, getValues, handleSubmit, register } = useForm<FormValues>({
    defaultValues: defaults(props.initialValues),
    mode: "onChange",
    resolver: zodResolver(schema),
    shouldFocusError: true,
  });
  const field = (name: keyof FormValues, child: ReactElement<Record<string, unknown>>) => (
    <Field error={errors[name]?.message} label={fieldLabels[name]} name={name}>{child}</Field>
  );

  return (
    <form className="request-form" onSubmit={(event) => void handleSubmit(props.onSubmit)(event)} noValidate>
      <p className="required-note"><span aria-hidden="true">*</span> Complete every field to enable submission. Incomplete work can be saved privately as a draft.</p>
      <FormErrorSummary errors={errors} />
      <FormSection description="Describe the need in plain language. Internal teams and routes are selected later." title="The need">
        {field("title", <input {...register("title")} />)}
        {field("serviceCategory", <select defaultValue="" {...register("serviceCategory")}><option disabled value="">Select a category</option><option>Advisory support</option><option>Data and reporting</option><option>Operational support</option><option>Research support</option></select>)}
        {field("description", <textarea rows={5} {...register("description")} />)}
        {field("questionToAnswer", <textarea rows={3} {...register("questionToAnswer")} />)}
        {field("desiredOutcome", <textarea rows={3} {...register("desiredOutcome")} />)}
        {field("backgroundContext", <textarea rows={4} {...register("backgroundContext")} />)}
      </FormSection>
      <FormSection description="Define what the work should cover and what it will support." title="Scope and purpose">
        {field("subjectAreaOrLocation", <textarea rows={3} {...register("subjectAreaOrLocation")} />)}
        <div className="form-grid">
          {field("coverageStart", <input type="date" {...register("coverageStart")} />)}
          {field("coverageEnd", <input type="date" {...register("coverageEnd")} />)}
        </div>
        {field("supportedActivityOrDecision", <textarea rows={3} {...register("supportedActivityOrDecision")} />)}
      </FormSection>
      <FormSection description="Set urgency, timing, format and the measure of success." title="Product expectations">
        <div className="form-grid">
          {field("customerUrgency", <select {...register("customerUrgency")}><option value="ROUTINE">Routine</option><option value="TIME_SENSITIVE">Time-sensitive</option><option value="IMMEDIATE">Immediate</option></select>)}
          {field("requiredBy", <input min={today()} type="date" {...register("requiredBy")} />)}
          {field("preferredDeliverableType", <select defaultValue="" {...register("preferredDeliverableType")}><option disabled value="">Select a type</option><option>Written report</option><option>Briefing note</option><option>Data summary</option><option>Presentation</option><option>Other</option></select>)}
        </div>
        {field("requiredByReason", <textarea rows={3} {...register("requiredByReason")} />)}
        {field("successCriteria", <textarea rows={3} {...register("successCriteria")} />)}
      </FormSection>
      <FormSection description="Record caveats, available material and any handling needs." title="Supporting information and handling">
        {field("constraintsOrCaveats", <textarea placeholder="Enter ‘No known constraints’ if none apply." rows={3} {...register("constraintsOrCaveats")} />)}
        {field("supportingInformation", <textarea placeholder="Describe available material, or enter ‘None available’." rows={3} {...register("supportingInformation")} />)}
        {field("sensitivity", <select {...register("sensitivity")}><option value="STANDARD">Standard</option><option value="SENSITIVE">Sensitive</option><option value="RESTRICTED">Restricted</option></select>)}
        {field("handlingInstructions", <textarea placeholder="State the required handling, or enter ‘Standard handling applies’." rows={3} {...register("handlingInstructions")} />)}
      </FormSection>
      <div className="form-actions form-actions--request">
        <button className="button button--primary" disabled={!isValid || props.disabled || props.draftDisabled} type="submit">{props.disabled ? "Submitting…" : "Submit request"}</button>
        {props.onSaveDraft ? <button className="button" disabled={props.disabled || props.draftDisabled} onClick={() => props.onSaveDraft?.(getValues())} type="button">{props.draftDisabled ? "Saving…" : "Save draft"}</button> : null}
        {props.hasDraft ? <button className="button button--danger" disabled={props.disabled || props.draftDisabled} onClick={props.onDeleteDraft} type="button">Delete draft</button> : null}
        <p>The released product will return to your dashboard. Authorised staff handle internal routing, assignment and release.</p>
      </div>
    </form>
  );
}

function FormErrorSummary({ errors }: { errors: FieldErrors<FormValues> }) {
  const fields = (Object.keys(fieldLabels) as (keyof FormValues)[]).filter((name) => errors[name]);
  if (fields.length === 0) return null;
  return <section className="form-error-summary" role="alert"><strong>Check the required fields</strong><ul>{fields.map((name) => <li key={name}><a href={`#request-${name}`}>{fieldLabels[name]}: {errors[name]?.message}</a></li>)}</ul></section>;
}

function FormSection({ children, description, title }: { children: ReactNode; description: string; title: string }) {
  return <fieldset className="form-section"><legend>{title}</legend><p>{description}</p>{children}</fieldset>;
}

function Field({ children, error, label, name }: { children: ReactElement<Record<string, unknown>>; error?: string; label: string; name: keyof FormValues }) {
  const id = `request-${name}`;
  const errorId = `${id}-error`;
  return <label className="form-field" htmlFor={id}><span>{label} <b aria-hidden="true">*</b><span className="sr-only"> required</span></span>{cloneElement(children, { id, required: true, "aria-invalid": Boolean(error), "aria-describedby": error ? errorId : undefined })}{error ? <small className="field-error" id={errorId} role="alert">{error}</small> : null}</label>;
}
