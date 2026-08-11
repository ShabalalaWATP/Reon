import { useId } from "react";
import type { UseFormRegister } from "react-hook-form";

import type { EligibleSpecialist } from "../../lib/api/types";
import type { WorkActionValues } from "./workActionModel";

export type SpecialistOptions = {
  items: EligibleSpecialist[];
  onRetry: () => void;
  status: "idle" | "loading" | "error" | "ready";
};

type Props = {
  error?: string;
  options: SpecialistOptions;
  register: UseFormRegister<WorkActionValues>;
};

export function EligibleSpecialistField({ error, options, register }: Props) {
  const selectId = useId();
  const errorId = `${selectId}-error`;
  const unavailable = options.status !== "ready" || options.items.length === 0;
  const prompt =
    options.status === "loading"
      ? "Loading eligible Analysts…"
      : options.status === "error"
        ? "Eligible Analysts unavailable"
        : options.items.length === 0
          ? "No eligible Analysts available"
          : "Select a Lead Analyst";

  return (
    <>
      <div className="form-field">
        <label htmlFor={selectId}>Lead Analyst</label>
        <select
          aria-describedby={error ? errorId : undefined}
          aria-invalid={Boolean(error)}
          defaultValue=""
          disabled={unavailable}
          id={selectId}
          {...register("specialistId")}
        >
          <option disabled value="">
            {prompt}
          </option>
          {options.items.map((specialist) => (
            <option key={specialist.id} value={specialist.id}>
              {specialist.displayName}
            </option>
          ))}
        </select>
        {error ? (
          <small className="field-error" id={errorId} role="alert">
            {error}
          </small>
        ) : null}
      </div>
      <SpecialistLoadState options={options} />
    </>
  );
}

function SpecialistLoadState({ options }: { options: SpecialistOptions }) {
  if (options.status === "loading") {
    return (
      <p className="specialist-state" role="status">
        Loading eligible Analysts…
      </p>
    );
  }
  if (options.status === "error") {
    return (
      <div className="specialist-state specialist-state--error" role="alert">
        <span>Eligible Analysts could not be loaded.</span>
        <button
          className="button button--secondary"
          onClick={options.onRetry}
          type="button"
        >
          Try again
        </button>
      </div>
    );
  }
  if (options.status === "ready" && options.items.length === 0) {
    return (
      <p className="specialist-state" role="status">
        No eligible Analysts are available for this team.
      </p>
    );
  }
  return null;
}
