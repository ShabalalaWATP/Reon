import { useId } from "react";
import type { UseFormRegister } from "react-hook-form";

import type { OrganisationUnit } from "../../lib/api/types";
import type { WorkActionValues } from "./workActionModel";

export type RoutingOptions = {
  items: OrganisationUnit[];
  onRetry: () => void;
  status: "idle" | "loading" | "error" | "ready";
};

type Props = {
  error?: string;
  options: RoutingOptions;
  register: UseFormRegister<WorkActionValues>;
  selectedId?: string;
};

const optionSuffix: Record<OrganisationUnit["staffingStatus"], string> = {
  ROUTING_POOL: "routing pool",
  STAFFED: "staffed",
  UNSTAFFED: "awaiting staffing",
};

export function RoutingDestinationField({
  error,
  options,
  register,
  selectedId,
}: Props) {
  const selectId = useId();
  const errorId = `${selectId}-error`;
  const unavailable = options.status !== "ready" || options.items.length === 0;
  const selected = options.items.find((item) => item.id === selectedId);
  const prompt =
    options.status === "loading"
      ? "Loading valid destinations…"
      : options.status === "error"
        ? "Valid destinations unavailable"
        : options.items.length === 0
          ? "No valid destinations available"
          : "Select a destination";

  return (
    <>
      <div className="form-field">
        <label htmlFor={selectId}>Destination unit</label>
        <select
          aria-describedby={error ? errorId : undefined}
          aria-invalid={Boolean(error)}
          defaultValue=""
          disabled={unavailable}
          id={selectId}
          {...register("destinationUnitId")}
        >
          <option disabled value="">{prompt}</option>
          {options.items.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name} · {optionSuffix[item.staffingStatus]}
            </option>
          ))}
        </select>
        {error ? <small className="field-error" id={errorId} role="alert">{error}</small> : null}
      </div>
      <RoutingLoadState options={options} />
      {selected?.kind === "TEAM" && selected.staffingStatus === "UNSTAFFED" ? (
        <p className="staffing-warning" role="status">
          {selected.name} is unstaffed. Work will await staffing after routing.
        </p>
      ) : null}
    </>
  );
}

function RoutingLoadState({ options }: { options: RoutingOptions }) {
  if (options.status === "loading") {
    return <p className="routing-state" role="status">Loading valid destinations…</p>;
  }
  if (options.status === "error") {
    return (
      <div className="routing-state routing-state--error" role="alert">
        <span>Valid destinations could not be loaded.</span>
        <button className="button button--secondary" onClick={options.onRetry} type="button">
          Try again
        </button>
      </div>
    );
  }
  if (options.status === "ready" && options.items.length === 0) {
    return <p className="routing-state" role="status">No valid destinations are configured for this task.</p>;
  }
  return null;
}
