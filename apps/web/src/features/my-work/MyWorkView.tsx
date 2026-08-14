import { Link } from "react-router";

import { PageState } from "../../components/PageState";
import type {
  ActionColumn,
  ActionFilters,
  ActionWorkspace,
  PersonalAction,
} from "../../lib/api/actionNotificationTypes";
import { ApiError } from "../../lib/api/client";
import { roleLabels } from "../../lib/routes";
import { ActionRegister } from "./ActionRegister";
import { FreshnessBanner, WorkCounts } from "./MyWorkSummary";
import { SavedViewControls } from "./SavedViewControls";
import {
  actionColumns,
  actionSections,
  actionTypeLabel,
  columnLabels,
  sectionLabels,
} from "./myWorkModel";
import { useMyWorkPage } from "./useMyWorkPage";

export function MyWorkView({
  controller,
  first,
  items,
}: {
  controller: ReturnType<typeof useMyWorkPage>;
  first: ActionWorkspace;
  items: PersonalAction[];
}) {
  const { columns, createView, deleteView, filters, query, session, setFilters, updateView } =
    controller;
  const actionTypes = [
    ...new Set([...items.map((item) => item.actionType), ...filters.actionTypes]),
  ].sort();
  return (
    <main className="page-stack my-work-page">
      <header className="page-heading">
        <div>
          <span>{roleLabels[session!.user.role]}</span>
          <h1>My actions</h1>
          <p>
            Work assigned to you, actions available to your unit and recent authorised progress.
          </p>
        </div>
        <Link className="button button--quiet" to="/notifications">
          Notifications
        </Link>
      </header>
      <WorkCounts first={first} filters={filters} setFilters={setFilters} />
      <FreshnessBanner first={first} />
      <WorkTools actionTypes={actionTypes} controller={controller} first={first} />
      <MutationError errors={[createView.error, updateView.error, deleteView.error]} />
      <WorkSections columns={columns} filters={filters} items={items} />
      <LoadMore
        hasNextPage={query.hasNextPage}
        isFetching={query.isFetchingNextPage}
        load={() => void query.fetchNextPage()}
      />
    </main>
  );
}

function WorkTools({
  actionTypes,
  controller,
  first,
}: {
  actionTypes: string[];
  controller: ReturnType<typeof useMyWorkPage>;
  first: ActionWorkspace;
}) {
  const {
    applyView,
    columns,
    createView,
    deleteView,
    filters,
    selectedView,
    setColumns,
    setFilters,
    setSelectedView,
    updateView,
  } = controller;
  return (
    <details className="work-tools">
      <summary>Saved views and filters</summary>
      <div className="work-tool-controls">
        <SavedViewControls
          columns={columns}
          filters={filters}
          onApply={applyView}
          onCreate={(name) => createView.mutate(name)}
          onDelete={(view) => deleteView.mutate(view)}
          onUpdate={(view) => updateView.mutate(view)}
          pending={createView.isPending || updateView.isPending || deleteView.isPending}
          selectedId={selectedView}
          setSelectedId={setSelectedView}
          views={first.savedViews}
        />
        <WorkFilters
          actionTypes={actionTypes}
          columns={columns}
          filters={filters}
          setColumns={setColumns}
          setFilters={setFilters}
        />
      </div>
    </details>
  );
}

function WorkFilters({
  actionTypes,
  columns,
  filters,
  setColumns,
  setFilters,
}: Pick<ReturnType<typeof useMyWorkPage>, "columns" | "filters" | "setColumns" | "setFilters"> & {
  actionTypes: string[];
}) {
  return (
    <div className="work-filters">
      <label className="form-field">
        <span>Action type</span>
        <select
          onChange={(event) =>
            setFilters((current) => ({
              ...current,
              actionTypes: event.target.value ? [event.target.value] : [],
            }))
          }
          value={filters.actionTypes[0] ?? ""}
        >
          <option value="">All action types</option>
          {actionTypes.map((type) => (
            <option key={type} value={type}>
              {actionTypeLabel(type)}
            </option>
          ))}
        </select>
      </label>
      <label className="form-field">
        <span>Due before</span>
        <input
          onChange={(event) =>
            setFilters((current) => ({ ...current, dueBefore: event.target.value || null }))
          }
          type="date"
          value={filters.dueBefore ?? ""}
        />
      </label>
      <ColumnPicker columns={columns} setColumns={setColumns} />
    </div>
  );
}

function ColumnPicker({
  columns,
  setColumns,
}: Pick<ReturnType<typeof useMyWorkPage>, "columns" | "setColumns">) {
  return (
    <fieldset className="column-picker">
      <legend>Visible columns</legend>
      {actionColumns.map((column) => (
        <label key={column}>
          <input
            checked={columns.includes(column)}
            disabled={columns.length === 1 && columns[0] === column}
            onChange={() =>
              setColumns((current) =>
                current.includes(column)
                  ? current.filter((value) => value !== column)
                  : [...current, column],
              )
            }
            type="checkbox"
          />
          {columnLabels[column]}
        </label>
      ))}
    </fieldset>
  );
}

function MutationError({ errors }: { errors: Array<Error | null> }) {
  const error = errors.find(Boolean);
  if (!error) return null;
  return (
    <p className="form-banner form-banner--error" role="alert">
      {error instanceof ApiError ? error.message : "The saved view could not be changed."}
    </p>
  );
}

function LoadMore({
  hasNextPage,
  isFetching,
  load,
}: {
  hasNextPage: boolean;
  isFetching: boolean;
  load: () => void;
}) {
  if (!hasNextPage) return null;
  return (
    <button className="button work-load-more" disabled={isFetching} onClick={load} type="button">
      {isFetching ? "Loading…" : "Load more"}
    </button>
  );
}

function WorkSections({
  columns,
  filters,
  items,
}: {
  columns: ActionColumn[];
  filters: ActionFilters;
  items: PersonalAction[];
}) {
  if (items.length === 0)
    return (
      <PageState kind="empty" title="No work in this view">
        Choose another section or saved view to broaden the result.
      </PageState>
    );
  const visibleSections = actionSections.filter(
    (section) => filters.sections.length === 0 || filters.sections.includes(section),
  );
  return (
    <>
      {visibleSections.map((section) => (
        <WorkSection
          columns={columns}
          items={items.filter((item) => item.section === section)}
          key={section}
          section={section}
        />
      ))}
    </>
  );
}

function WorkSection({
  columns,
  items,
  section,
}: {
  columns: ActionColumn[];
  items: PersonalAction[];
  section: PersonalAction["section"];
}) {
  if (items.length === 0) return null;
  return (
    <section className="work-section" aria-labelledby={`work-${section}`}>
      <div className="section-heading">
        <span>
          {items.length} item{items.length === 1 ? "" : "s"}
        </span>
        <h2 id={`work-${section}`}>{sectionLabels[section]}</h2>
      </div>
      <ActionRegister
        columns={columns}
        items={items}
        label={`${sectionLabels[section]} action register`}
      />
    </section>
  );
}
