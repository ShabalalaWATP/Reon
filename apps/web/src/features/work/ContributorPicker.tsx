import { useId } from "react";
import type { UseFormRegister } from "react-hook-form";

import type { EligibleSpecialist } from "../../lib/api/types";
import type { WorkActionValues } from "./workActionModel";

type Props = {
  error?: string;
  items: EligibleSpecialist[];
  leadAnalystId?: string;
  register: UseFormRegister<WorkActionValues>;
  selectedIds: string[];
};

export function ContributorPicker({
  error,
  items,
  leadAnalystId,
  register,
  selectedIds,
}: Props) {
  const groupId = useId();
  const helpId = `${groupId}-help`;
  const errorId = `${groupId}-error`;
  const selectedCount = selectedIds.filter((id) => id !== leadAnalystId).length;
  const describedBy = [helpId, error ? errorId : null].filter(Boolean).join(" ");

  return (
    <fieldset
      aria-describedby={describedBy}
      aria-invalid={Boolean(error)}
      className="contributor-picker"
    >
      <legend>
        Contributing Analysts <small>Optional, choose up to 10</small>
      </legend>
      <p className="contributor-picker__help" id={helpId}>
        Select every Analyst who will support the Lead. Each choice can be turned on or off independently.
      </p>
      <div className="contributor-picker__options">
        {items.map((analyst) => {
          const isLead = analyst.id === leadAnalystId;
          return (
            <label
              className={`contributor-choice${isLead ? " contributor-choice--lead" : ""}`}
              key={analyst.id}
            >
              <input
                disabled={isLead}
                type="checkbox"
                value={analyst.id}
                {...register("contributorIds")}
              />
              <span>
                <strong>{analyst.displayName}</strong>
                <small>{isLead ? "Selected as Lead" : "Add as Contributor"}</small>
              </span>
            </label>
          );
        })}
      </div>
      <p aria-live="polite" className="contributor-picker__count">
        {selectedCount} {selectedCount === 1 ? "Contributor" : "Contributors"} selected
      </p>
      {error ? (
        <small className="field-error" id={errorId} role="alert">
          {error}
        </small>
      ) : null}
    </fieldset>
  );
}
