import { zodResolver } from "@hookform/resolvers/zod";
import type { ReactElement } from "react";
import { useForm } from "react-hook-form";

import type { RequestCreateInput, RequestDraftInput } from "../../lib/api/types";
import {
  incompleteFields,
  invalidRequestFields,
  requestFormDefaults,
  requestFormSchema,
  requestFormSections,
  requestTextLimits,
  type RequestFormValues,
} from "./requestFormModel";
import { FormErrorSummary, RequestField, RequestProgress } from "./RequestFormPresentation";
import { RequestFormSections } from "./RequestFormSections";

type Props = {
  disabled: boolean;
  draftDisabled?: boolean;
  hasDraft?: boolean;
  initialValues?: RequestDraftInput;
  onDeleteDraft?: () => void;
  onSaveDraft?: (input: RequestDraftInput) => void;
  onSubmit: (input: RequestCreateInput) => void;
};

export function RequestForm(props: Props) {
  const {
    formState: { errors, isValid },
    getValues,
    handleSubmit,
    register,
    watch,
  } = useForm<RequestFormValues>({
    defaultValues: requestFormDefaults(props.initialValues),
    mode: "onChange",
    resolver: zodResolver(requestFormSchema),
    shouldFocusError: true,
  });
  const values = watch();
  const invalidFields = invalidRequestFields(values);
  const remaining = (index: number) => incompleteFields(requestFormSections[index], invalidFields);
  const field = (name: keyof RequestFormValues, child: ReactElement<Record<string, unknown>>) => {
    const maximum = requestTextLimits[name];
    const count = maximum ? { length: values[name].length, max: maximum } : undefined;
    return (
      <RequestField count={count} error={errors[name]?.message} name={name}>
        {child}
      </RequestField>
    );
  };

  return (
    <form
      className="request-form"
      onSubmit={(event) => void handleSubmit(props.onSubmit)(event)}
      noValidate
    >
      <p className="required-note">
        <span aria-hidden="true">*</span> Complete every field to enable submission. Incomplete work
        can be saved privately as a draft.
      </p>
      <RequestProgress invalidFields={invalidFields} />
      <FormErrorSummary errors={errors} />
      <RequestFormSections
        complete={(index) => remaining(index) === 0}
        field={field}
        register={register}
      />
      <RequestFormActions
        disabled={props.disabled}
        draftDisabled={Boolean(props.draftDisabled)}
        hasDraft={Boolean(props.hasDraft)}
        isValid={isValid}
        onDeleteDraft={props.onDeleteDraft}
        onSaveDraft={props.onSaveDraft ? () => props.onSaveDraft?.(getValues()) : undefined}
      />
    </form>
  );
}

function RequestFormActions({
  disabled,
  draftDisabled,
  hasDraft,
  isValid,
  onDeleteDraft,
  onSaveDraft,
}: {
  disabled: boolean;
  draftDisabled: boolean;
  hasDraft: boolean;
  isValid: boolean;
  onDeleteDraft?: () => void;
  onSaveDraft?: () => void;
}) {
  return (
    <div className="form-actions form-actions--request">
      <button
        className="button button--primary"
        disabled={!isValid || disabled || draftDisabled}
        type="submit"
      >
        {disabled ? "Submitting…" : "Submit request"}
      </button>
      {onSaveDraft ? (
        <button
          className="button"
          disabled={disabled || draftDisabled}
          onClick={onSaveDraft}
          type="button"
        >
          {draftDisabled ? "Saving…" : "Save draft"}
        </button>
      ) : null}
      {hasDraft ? (
        <button
          className="button button--danger"
          disabled={disabled || draftDisabled}
          onClick={onDeleteDraft}
          type="button"
        >
          Delete draft
        </button>
      ) : null}
      <p>
        The released product will return to your dashboard. Authorised staff handle internal
        routing, assignment and release.
      </p>
    </div>
  );
}
