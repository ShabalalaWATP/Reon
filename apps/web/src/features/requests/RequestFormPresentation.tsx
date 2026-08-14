import { cloneElement, type ReactElement, type ReactNode } from "react";
import type { FieldErrors } from "react-hook-form";

import {
  incompleteFields,
  requestFieldLabels,
  requestFormSections,
  type RequestFormValues,
  type RequestSectionDefinition,
} from "./requestFormModel";

export function RequestProgress({ invalidFields }: { invalidFields: ReadonlySet<string> }) {
  return (
    <nav aria-label="Form progress" className="request-progress">
      {requestFormSections.map((section, index) => (
        <ProgressStep
          index={index}
          key={section.id}
          remaining={incompleteFields(section, invalidFields)}
          section={section}
        />
      ))}
    </nav>
  );
}

function ProgressStep({
  index,
  remaining,
  section,
}: {
  index: number;
  remaining: number;
  section: RequestSectionDefinition;
}) {
  const complete = remaining === 0;
  const countLabel = `${remaining} field${remaining === 1 ? "" : "s"} left`;
  return (
    <a
      className={
        complete
          ? "request-progress__step request-progress__step--complete"
          : "request-progress__step"
      }
      href={`#request-section-${section.id}`}
    >
      <i aria-hidden="true">{complete ? "✓" : String(index + 1).padStart(2, "0")}</i>
      <span>
        <strong>{section.title}</strong>
        <small>{complete ? "Complete" : countLabel}</small>
      </span>
    </a>
  );
}

export function FormErrorSummary({ errors }: { errors: FieldErrors<RequestFormValues> }) {
  const fields = (Object.keys(requestFieldLabels) as (keyof RequestFormValues)[]).filter(
    (name) => errors[name],
  );
  if (fields.length === 0) return null;
  return (
    <section className="form-error-summary" role="alert">
      <strong>Check the required fields</strong>
      <ul>
        {fields.map((name) => (
          <li key={name}>
            <a href={`#request-${name}`}>
              {requestFieldLabels[name]}: {errors[name]?.message}
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function FormSection({
  children,
  complete,
  section,
}: {
  children: ReactNode;
  complete: boolean;
  section: RequestSectionDefinition;
}) {
  return (
    <fieldset
      className={complete ? "form-section form-section--complete" : "form-section"}
      id={`request-section-${section.id}`}
    >
      <legend>
        {section.title}
        {complete ? <span className="sr-only"> — complete</span> : null}
      </legend>
      <p>{section.description}</p>
      {children}
    </fieldset>
  );
}

export function RequestField({
  children,
  count,
  error,
  name,
}: {
  children: ReactElement<Record<string, unknown>>;
  count?: { length: number; max: number };
  error?: string;
  name: keyof RequestFormValues;
}) {
  const id = `request-${name}`;
  const errorId = `${id}-error`;
  const nearLimit = count !== undefined && count.length >= count.max * 0.9;
  return (
    <div className="form-field">
      <span className="form-field__label-row">
        <label htmlFor={id}>
          {requestFieldLabels[name]} <b aria-hidden="true">*</b>
          <span className="sr-only"> required</span>
        </label>
        {count ? (
          <small
            aria-hidden="true"
            className={nearLimit ? "char-counter char-counter--limit" : "char-counter"}
          >
            {count.length.toLocaleString("en-GB")} / {count.max.toLocaleString("en-GB")}
          </small>
        ) : null}
      </span>
      {cloneElement(children, {
        id,
        required: true,
        "aria-invalid": Boolean(error),
        "aria-describedby": error ? errorId : undefined,
      })}
      {error ? (
        <small className="field-error" id={errorId} role="alert">
          {error}
        </small>
      ) : null}
    </div>
  );
}
