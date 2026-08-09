import { GitBranch, Search, UsersRound, X } from "lucide-react";
import { useMemo, type CSSProperties } from "react";

import type { ConfigurationEdgeDraft, ConfigurationUnitDraft } from "../../lib/api/configurationTypes";
import { configurationRows, filterConfigurationRows, matchesConfigurationRow, unitState } from "./configurationModel";

export function ConfigurationTree({
  edges,
  effectiveAt,
  onSearchChange,
  onSelect,
  search,
  selectedId,
  units,
}: {
  edges: ConfigurationEdgeDraft[];
  effectiveAt: string;
  onSearchChange: (value: string) => void;
  onSelect: (unitId: string) => void;
  search: string;
  selectedId: string | null;
  units: ConfigurationUnitDraft[];
}) {
  const rows = useMemo(() => configurationRows(units, edges, effectiveAt), [edges, effectiveAt, units]);
  const visibleRows = useMemo(() => filterConfigurationRows(rows, search), [rows, search]);
  if (!rows.length) return <p className="inline-empty">No organisation units have been configured.</p>;
  const moveFocus = (index: number) => {
    const target = document.getElementById(`configuration-unit-${visibleRows[index]?.unitId}`);
    target?.focus();
  };
  return (
    <div className="configuration-tree-panel">
      <label className="configuration-tree-search">
        <span>Search organisation</span>
        <span><Search aria-hidden="true" size={16} /><input onChange={(event) => onSearchChange(event.target.value)} placeholder="Name, code or unit type" type="search" value={search} />{search ? <button aria-label="Clear organisation search" onClick={() => onSearchChange("")} type="button"><X aria-hidden="true" size={15} /></button> : null}</span>
      </label>
      <p aria-live="polite" className="configuration-tree-results">{search.trim() ? `${visibleRows.filter((row) => matchesConfigurationRow(row, search)).length} matching units, with organisational context` : `${rows.length} organisation units`}</p>
      {!visibleRows.length ? <p className="inline-empty" role="status">No organisation units match “{search.trim()}”.</p> : <div aria-label="Organisation hierarchy" className="configuration-tree" role="tree">
      {visibleRows.map((unit, index) => (
        <button
          aria-level={unit.depth + 1}
          aria-selected={selectedId === unit.unitId}
          className={selectedId === unit.unitId ? "configuration-tree__item configuration-tree__item--selected" : "configuration-tree__item"}
          id={`configuration-unit-${unit.unitId}`}
          key={unit.unitId}
          onClick={() => onSelect(unit.unitId)}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown") { event.preventDefault(); moveFocus(Math.min(index + 1, visibleRows.length - 1)); }
            if (event.key === "ArrowUp") { event.preventDefault(); moveFocus(Math.max(index - 1, 0)); }
            if (event.key === "Home") { event.preventDefault(); moveFocus(0); }
            if (event.key === "End") { event.preventDefault(); moveFocus(visibleRows.length - 1); }
          }}
          role="treeitem"
          style={{ "--tree-depth": unit.depth } as CSSProperties}
          type="button"
        >
          <span>{unit.kind === "TEAM" ? <UsersRound aria-hidden="true" size={16} /> : <GitBranch aria-hidden="true" size={16} />}</span>
          <span><strong>{unit.name}</strong><small>{unit.code} · {unit.kind.replace("_", " ").toLowerCase()}</small></span>
          <em>{unitState(unit)}</em>
        </button>
      ))}</div>}
    </div>
  );
}
