import { useState, type FormEvent } from "react";

import type { ActionColumn, ActionFilters, SavedActionView } from "../../lib/api/actionNotificationTypes";

type Props = {
  columns: ActionColumn[];
  filters: ActionFilters;
  onApply: (view: SavedActionView) => void;
  onCreate: (name: string) => void;
  onDelete: (view: SavedActionView) => void;
  onUpdate: (view: SavedActionView) => void;
  pending: boolean;
  selectedId: string;
  setSelectedId: (id: string) => void;
  views: SavedActionView[];
};

export function SavedViewControls(props: Props) {
  const [name, setName] = useState("");
  const selected = props.views.find((view) => view.id === props.selectedId);
  const create = (event: FormEvent) => {
    event.preventDefault();
    if (name.trim().length >= 2) { props.onCreate(name.trim()); setName(""); }
  };
  return <div className="saved-view-controls">
    <label className="form-field"><span>Saved view</span><select onChange={(event) => { const view = props.views.find((candidate) => candidate.id === event.target.value); props.setSelectedId(event.target.value); if (view) props.onApply(view); }} value={props.selectedId}><option value="">Current filters</option>{props.views.map((view) => <option key={view.id} value={view.id}>{view.name}</option>)}</select></label>
    {selected ? <><button className="button" disabled={props.pending} onClick={() => props.onUpdate(selected)} type="button">Update view</button><button className="button button--quiet" disabled={props.pending} onClick={() => props.onDelete(selected)} type="button">Delete view</button></> : <form onSubmit={create}><label className="form-field"><span>Save current view</span><input maxLength={80} onChange={(event) => setName(event.target.value)} placeholder="View name" value={name} /></label><button className="button" disabled={props.pending || name.trim().length < 2} type="submit">Save view</button></form>}
    <span className="sr-only">{props.filters.sections.length} section filters and {props.columns.length} columns selected.</span>
  </div>;
}
