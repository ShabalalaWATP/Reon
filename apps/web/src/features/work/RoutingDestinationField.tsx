import { useId, useState } from "react";
import type { UseFormRegister } from "react-hook-form";

import type { OrganisationUnit, RoutingPathUnit } from "../../lib/api/types";
import type { WorkActionValues } from "./workActionModel";

export type RoutingOptions = {
  items: OrganisationUnit[];
  onRetry: () => void;
  route?: RoutingPathUnit[];
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
  const searchId = `${selectId}-search`;
  const errorId = `${selectId}-error`;
  const [query, setQuery] = useState("");
  const search = query.trim().toLocaleLowerCase("en-GB");
  const matchingItems = search
    ? options.items.filter((item) =>
        `${item.name} ${item.code}`.toLocaleLowerCase("en-GB").includes(search),
      )
    : options.items;
  const selected = options.items.find((item) => item.id === selectedId);
  const retainedSelection = selected
    && !matchingItems.some((item) => item.id === selected.id)
    ? selected
    : undefined;
  const unavailable = options.status !== "ready"
    || (matchingItems.length === 0 && !retainedSelection);
  const prompt = routingPrompt(options, matchingItems.length);

  return (
    <>
      {options.route?.length ? <RoutingBreadcrumbs route={options.route} /> : null}
      {options.status === "ready" && options.items.length > 0 ? (
        <div className="form-field routing-search">
          <label htmlFor={searchId}>Find destination</label>
          <input
            autoComplete="off"
            id={searchId}
            maxLength={120}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by name or code"
            type="search"
            value={query}
          />
          <small aria-live="polite">
            {matchingItems.length} of {options.items.length} destinations shown
          </small>
        </div>
      ) : null}
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
          {retainedSelection ? (
            <optgroup label="Selected destination">
              <DestinationOption item={retainedSelection} />
            </optgroup>
          ) : null}
          {matchingItems.map((item) => (
            <DestinationOption item={item} key={item.id} />
          ))}
        </select>
        {error ? <small className="field-error" id={errorId} role="alert">{error}</small> : null}
      </div>
      <RoutingLoadState options={options} />
      {options.status === "ready" && options.items.length > 0 && matchingItems.length === 0 ? (
        <p className="routing-state">No destination matches this name or code.</p>
      ) : null}
      {selected ? (
        <p aria-live="polite" className="routing-selection-summary">
          Selected route: {[...(options.route ?? []), selected].map(unitLabel).join(" › ")}
        </p>
      ) : null}
      {selected?.kind === "TEAM" && selected.staffingStatus === "UNSTAFFED" ? (
        <p className="staffing-warning" role="status">
          {selected.name} is unstaffed. Work will await staffing after routing.
        </p>
      ) : null}
    </>
  );
}

function DestinationOption({ item }: { item: OrganisationUnit }) {
  return (
    <option value={item.id}>
      {item.name} · {optionSuffix[item.staffingStatus]}
    </option>
  );
}

function RoutingBreadcrumbs({ route }: { route: RoutingPathUnit[] }) {
  return (
    <nav aria-label="Current routing path" className="routing-breadcrumbs">
      <span>Current path</span>
      <ol>{route.map((unit) => <li key={unit.id}>{unitLabel(unit)}</li>)}</ol>
    </nav>
  );
}

function unitLabel(unit: Pick<OrganisationUnit, "code" | "name">) {
  return unit.name === unit.code ? unit.name : `${unit.name} (${unit.code})`;
}

function routingPrompt(options: RoutingOptions, visibleCount: number) {
  if (options.status === "loading") return "Loading valid destinations…";
  if (options.status === "error") return "Valid destinations unavailable";
  if (options.items.length === 0) return "No valid destinations available";
  return visibleCount === 0 ? "No matching destinations" : "Select a destination";
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
