import type { ReactElement, ReactNode } from "react";
import type { UseFormRegister } from "react-hook-form";

import { requestFormSections, requestToday, type RequestFormValues } from "./requestFormModel";
import { FormSection } from "./RequestFormPresentation";

export type RequestFieldRenderer = (
  name: keyof RequestFormValues,
  child: ReactElement<Record<string, unknown>>,
) => ReactNode;

type Props = {
  complete: (sectionIndex: number) => boolean;
  field: RequestFieldRenderer;
  register: UseFormRegister<RequestFormValues>;
};

export function RequestFormSections({ complete, field, register }: Props) {
  return (
    <>
      <FormSection complete={complete(0)} section={requestFormSections[0]}>
        {field("title", <input {...register("title")} />)}
        {field("description", <textarea rows={5} {...register("description")} />)}
        {field("questionToAnswer", <textarea rows={3} {...register("questionToAnswer")} />)}
        {field("desiredOutcome", <textarea rows={3} {...register("desiredOutcome")} />)}
        {field("backgroundContext", <textarea rows={4} {...register("backgroundContext")} />)}
      </FormSection>
      <FormSection complete={complete(1)} section={requestFormSections[1]}>
        {field(
          "subjectAreaOrLocation",
          <textarea rows={3} {...register("subjectAreaOrLocation")} />,
        )}
        <div className="form-grid">
          {field("coverageStart", <input type="date" {...register("coverageStart")} />)}
          {field("coverageEnd", <input type="date" {...register("coverageEnd")} />)}
        </div>
        {field(
          "supportedActivityOrDecision",
          <textarea rows={3} {...register("supportedActivityOrDecision")} />,
        )}
      </FormSection>
      <FormSection complete={complete(2)} section={requestFormSections[2]}>
        <div className="form-grid">
          {field(
            "customerUrgency",
            <select {...register("customerUrgency")}>
              <option value="ROUTINE">Routine</option>
              <option value="TIME_SENSITIVE">Time-sensitive</option>
              <option value="IMMEDIATE">Immediate</option>
            </select>,
          )}
          {field(
            "requiredBy",
            <input min={requestToday()} type="date" {...register("requiredBy")} />,
          )}
          {field(
            "preferredDeliverableType",
            <select defaultValue="" {...register("preferredDeliverableType")}>
              <option disabled value="">
                Select a type
              </option>
              <option>Written report</option>
              <option>Briefing note</option>
              <option>Data summary</option>
              <option>Presentation</option>
              <option>Other</option>
            </select>,
          )}
        </div>
        {field("requiredByReason", <textarea rows={3} {...register("requiredByReason")} />)}
        {field("successCriteria", <textarea rows={3} {...register("successCriteria")} />)}
      </FormSection>
      <FormSection complete={complete(3)} section={requestFormSections[3]}>
        {field(
          "constraintsOrCaveats",
          <textarea
            placeholder="Enter ‘No known constraints’ if none apply."
            rows={3}
            {...register("constraintsOrCaveats")}
          />,
        )}
        {field(
          "supportingInformation",
          <textarea
            placeholder="Describe available material, or enter ‘None available’."
            rows={3}
            {...register("supportingInformation")}
          />,
        )}
        {field(
          "sensitivity",
          <select {...register("sensitivity")}>
            <option value="STANDARD">Standard</option>
            <option value="SENSITIVE">Sensitive</option>
            <option value="RESTRICTED">Restricted</option>
          </select>,
        )}
        {field(
          "handlingInstructions",
          <textarea
            placeholder="State the required handling, or enter ‘Standard handling applies’."
            rows={3}
            {...register("handlingInstructions")}
          />,
        )}
      </FormSection>
    </>
  );
}
