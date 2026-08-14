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
  ROUTING_POOL: "routing function",
  STAFFED: "team staffed",
  UNSTAFFED: "team awaiting staffing",
};

export function RoutingDestinationField({ error, options, register, selectedId }: Props) {
  const selectId = useId();
  const searchId = `${selectId}-search`;
  const errorId = `${selectId}-error`;
  const [query, setQuery] = useState("");
  const state = destinationState(options, selectedId, query);

  return (
    <>
      <CurrentRoute route={options.route} />
      <DestinationSearch
        matchingCount={state.matchingItems.length}
        onChange={setQuery}
        options={options}
        query={query}
        searchId={searchId}
      />
      <div className="form-field">
        <label htmlFor={selectId}>Destination unit</label>
        <select
          aria-describedby={error ? errorId : undefined}
          aria-invalid={Boolean(error)}
          defaultValue=""
          disabled={state.unavailable}
          id={selectId}
          {...register("destinationUnitId")}
        >
          <option disabled value="">
            {state.prompt}
          </option>
          <DestinationOptions state={state} />
        </select>
        {error ? (
          <small className="field-error" id={errorId} role="alert">
            {error}
          </small>
        ) : null}
      </div>
      <RoutingLoadState options={options} />
      <NoDestinationMatch options={options} state={state} />
      <SelectedRoute route={options.route} selected={state.selected} />
      <StaffingWarning selected={state.selected} />
    </>
  );
}

type DestinationState = {
  matchingItems: OrganisationUnit[];
  prompt: string;
  retainedSelection?: OrganisationUnit;
  selected?: OrganisationUnit;
  unavailable: boolean;
};

function destinationState(
  options: RoutingOptions,
  selectedId: string | undefined,
  query: string,
): DestinationState {
  const search = query.trim().toLocaleLowerCase("en-GB");
  const matchingItems = search
    ? options.items.filter((item) =>
        `${item.name} ${item.code}`.toLocaleLowerCase("en-GB").includes(search),
      )
    : options.items;
  const selected = options.items.find((item) => item.id === selectedId);
  const selectionVisible = matchingItems.some((item) => item.id === selected?.id);
  const retainedSelection = selected && !selectionVisible ? selected : undefined;
  return {
    matchingItems,
    prompt: routingPrompt(options, matchingItems.length),
    retainedSelection,
    selected,
    unavailable:
      options.status !== "ready" || (matchingItems.length === 0 && retainedSelection === undefined),
  };
}

function CurrentRoute({ route }: { route?: RoutingPathUnit[] }) {
  if (!route?.length) return null;
  return <RoutingBreadcrumbs route={route} />;
}

function DestinationSearch({
  matchingCount,
  onChange,
  options,
  query,
  searchId,
}: {
  matchingCount: number;
  onChange: (value: string) => void;
  options: RoutingOptions;
  query: string;
  searchId: string;
}) {
  if (options.status !== "ready" || options.items.length === 0) return null;
  return (
    <div className="form-field routing-search">
      <label htmlFor={searchId}>Find destination</label>
      <input
        autoComplete="off"
        id={searchId}
        maxLength={120}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Search by name or code"
        type="search"
        value={query}
      />
      <small aria-live="polite">
        {matchingCount} of {options.items.length} destinations shown
      </small>
    </div>
  );
}

function DestinationOptions({ state }: { state: DestinationState }) {
  return (
    <>
      {state.retainedSelection ? (
        <optgroup label="Selected destination">
          <DestinationOption item={state.retainedSelection} />
        </optgroup>
      ) : null}
      {state.matchingItems.map((item) => (
        <DestinationOption item={item} key={item.id} />
      ))}
    </>
  );
}

function NoDestinationMatch({
  options,
  state,
}: {
  options: RoutingOptions;
  state: DestinationState;
}) {
  if (options.status !== "ready" || options.items.length === 0 || state.matchingItems.length > 0)
    return null;
  return <p className="routing-state">No destination matches this name or code.</p>;
}

function SelectedRoute({
  route,
  selected,
}: {
  route?: RoutingPathUnit[];
  selected?: OrganisationUnit;
}) {
  if (!selected) return null;
  return (
    <p aria-live="polite" className="routing-selection-summary">
      Selected route: {[...(route ?? []), selected].map(unitLabel).join(" › ")}
    </p>
  );
}

function StaffingWarning({ selected }: { selected?: OrganisationUnit }) {
  if (selected?.kind !== "TEAM" || selected.staffingStatus !== "UNSTAFFED") return null;
  return (
    <p className="staffing-warning" role="status">
      {selected.name} is unstaffed. Work will await staffing after routing.
    </p>
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
      <ol>
        {route.map((unit) => (
          <li key={unit.id}>{unitLabel(unit)}</li>
        ))}
      </ol>
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
    return (
      <p className="routing-state" role="status">
        Loading valid destinations…
      </p>
    );
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
    return (
      <p className="routing-state" role="status">
        No valid destinations are configured for this task.
      </p>
    );
  }
  return null;
}
