import { zodResolver } from "@hookform/resolvers/zod";
import { cloneElement, type ReactElement, type ReactNode } from "react";
import { useForm, type FieldErrors } from "react-hook-form";
import { z } from "zod";

import type { RequestCreateInput, RequestDraftInput } from "../../lib/api/types";

const today = () => new Date().toISOString().slice(0, 10);
const requiredText = (minimum: number, message: string, maximum: number) =>
  z.string().trim().min(minimum, message).max(maximum);

const schema = z.object({
  title: requiredText(3, "Enter a clear request title.", 160),
  serviceCategory: requiredText(2, "Choose a service category.", 80),
  description: requiredText(20, "Describe the need in at least 20 characters.", 5000),
  desiredOutcome: requiredText(10, "Describe the desired outcome.", 2000),
  backgroundContext: requiredText(1, "Add the known background and context.", 5000),
  requiredBy: z.string().min(1, "Choose a required-by date.").refine(
    (value) => value >= today(),
    "The required-by date cannot be in the past.",
  ),
  requiredByReason: requiredText(5, "Explain why this date matters.", 1000),
  preferredDeliverableType: requiredText(2, "Choose a product type.", 80),
  successCriteria: requiredText(5, "Describe how success will be assessed.", 2000),
  requestingBusinessArea: requiredText(2, "A requesting business area is required.", 120),
  intendedRecipients: z.string().refine(
    (value) => value.split("\n").some((recipient) => recipient.trim()),
    "Add at least one intended recipient.",
  ),
  sensitivity: z.enum(["STANDARD", "SENSITIVE", "RESTRICTED"]),
  handlingInstructions: requiredText(
    1,
    "Add handling instructions, or state that standard handling applies.",
    2000,
  ),
});

type FormValues = z.infer<typeof schema>;
type Props = {
  businessArea: string;
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
  desiredOutcome: "Desired outcome",
  backgroundContext: "Background and known context",
  requiredBy: "Required-by date",
  requiredByReason: "Why the date matters",
  preferredDeliverableType: "Preferred product type",
  successCriteria: "Success criteria",
  requestingBusinessArea: "Requesting business area",
  intendedRecipients: "Intended recipients",
  sensitivity: "Sensitivity",
  handlingInstructions: "Handling instructions",
};

function defaults(businessArea: string, draft?: RequestDraftInput): FormValues {
  return {
    title: draft?.title ?? "",
    serviceCategory: draft?.serviceCategory ?? "",
    description: draft?.description ?? "",
    desiredOutcome: draft?.desiredOutcome ?? "",
    backgroundContext: draft?.backgroundContext ?? "",
    requiredBy: draft?.requiredBy ?? "",
    requiredByReason: draft?.requiredByReason ?? "",
    preferredDeliverableType: draft?.preferredDeliverableType ?? "",
    successCriteria: draft?.successCriteria ?? "",
    requestingBusinessArea: businessArea,
    intendedRecipients: draft?.intendedRecipients?.join("\n") ?? "",
    sensitivity: draft?.sensitivity ?? "STANDARD",
    handlingInstructions: draft?.handlingInstructions ?? "",
  };
}

function recipients(value: string) {
  return value.split("\n").map((item) => item.trim()).filter(Boolean);
}

function draftInput(values: FormValues): RequestDraftInput {
  return {
    ...values,
    requiredBy: values.requiredBy || null,
    intendedRecipients: recipients(values.intendedRecipients),
  };
}

export function RequestForm(props: Props) {
  const {
    formState: { errors },
    getValues,
    handleSubmit,
    register,
  } = useForm<FormValues>({
    defaultValues: defaults(props.businessArea, props.initialValues),
    resolver: zodResolver(schema),
    shouldFocusError: true,
  });
  const error = (name: keyof FormValues) => errors[name]?.message;
  const field = (name: keyof FormValues, child: ReactElement<Record<string, unknown>>) => (
    <Field error={error(name)} label={fieldLabels[name]} name={name}>{child}</Field>
  );

  return (
    <form className="request-form" onSubmit={(event) => void handleSubmit((values) => props.onSubmit({ ...values, intendedRecipients: recipients(values.intendedRecipients) }))(event)} noValidate>
      <p className="required-note"><span aria-hidden="true">*</span> All fields are required before submission. Incomplete work can be saved privately as a draft.</p>
      <FormErrorSummary errors={errors} />
      <FormSection description="Define what is needed and the result you expect." title="The need">
        {field("title", <input {...register("title")} />)}
        {field("serviceCategory", <select defaultValue="" {...register("serviceCategory")}><option disabled value="">Select a category</option><option>Advisory support</option><option>Data and reporting</option><option>Operational support</option><option>Research support</option></select>)}
        {field("description", <textarea rows={5} {...register("description")} />)}
        {field("desiredOutcome", <textarea rows={3} {...register("desiredOutcome")} />)}
        {field("backgroundContext", <textarea rows={4} {...register("backgroundContext")} />)}
      </FormSection>
      <FormSection description="Set the timing, format and measure of success." title="Product expectations">
        <div className="form-grid">
          {field("requiredBy", <input min={today()} type="date" {...register("requiredBy")} />)}
          {field("preferredDeliverableType", <select defaultValue="" {...register("preferredDeliverableType")}><option disabled value="">Select a type</option><option>Written response</option><option>Briefing note</option><option>Data summary</option><option>Action plan</option></select>)}
        </div>
        {field("requiredByReason", <textarea rows={3} {...register("requiredByReason")} />)}
        {field("successCriteria", <textarea rows={3} {...register("successCriteria")} />)}
      </FormSection>
      <FormSection description="Confirm the business area, recipients and handling needs." title="Recipients and handling">
        {field("requestingBusinessArea", <input readOnly {...register("requestingBusinessArea")} />)}
        {field("intendedRecipients", <textarea placeholder="One recipient or group per line" rows={3} {...register("intendedRecipients")} />)}
        {field("sensitivity", <select {...register("sensitivity")}><option value="STANDARD">Standard</option><option value="SENSITIVE">Sensitive</option><option value="RESTRICTED">Restricted</option></select>)}
        {field("handlingInstructions", <textarea placeholder="State the required handling, or enter ‘Standard handling applies’." rows={3} {...register("handlingInstructions")} />)}
      </FormSection>
      <div className="form-actions form-actions--request">
        <button className="button button--primary" disabled={props.disabled || props.draftDisabled} type="submit">{props.disabled ? "Submitting…" : "Submit request"}</button>
        {props.onSaveDraft ? <button className="button" disabled={props.disabled || props.draftDisabled} onClick={() => props.onSaveDraft?.(draftInput(getValues()))} type="button">{props.draftDisabled ? "Saving…" : "Save draft"}</button> : null}
        {props.hasDraft ? <button className="button button--danger" disabled={props.disabled || props.draftDisabled} onClick={props.onDeleteDraft} type="button">Delete draft</button> : null}
        <p>A team and Analyst will be selected later by the responsible routing users and Team Manager.</p>
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
