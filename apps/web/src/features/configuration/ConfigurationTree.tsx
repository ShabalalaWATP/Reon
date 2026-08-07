import { GitBranch, UsersRound } from "lucide-react";
import type { CSSProperties } from "react";

import type { ConfigurationEdgeDraft, ConfigurationUnitDraft } from "../../lib/api/configurationTypes";
import { configurationRows, unitState } from "./configurationModel";

export function ConfigurationTree({
  edges,
  onSelect,
  selectedId,
  units,
}: {
  edges: ConfigurationEdgeDraft[];
  onSelect: (unitId: string) => void;
  selectedId: string | null;
  units: ConfigurationUnitDraft[];
}) {
  const rows = configurationRows(units, edges);
  if (!rows.length) return <p className="inline-empty">This draft has no organisation units.</p>;
  const moveFocus = (index: number) => {
    const target = document.getElementById(`configuration-unit-${rows[index]?.unitId}`);
    target?.focus();
  };
  return (
    <div aria-label="Draft organisation hierarchy" className="configuration-tree" role="tree">
      {rows.map((unit, index) => (
        <button
          aria-level={unit.depth + 1}
          aria-selected={selectedId === unit.unitId}
          className={selectedId === unit.unitId ? "configuration-tree__item configuration-tree__item--selected" : "configuration-tree__item"}
          id={`configuration-unit-${unit.unitId}`}
          key={unit.unitId}
          onClick={() => onSelect(unit.unitId)}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown") { event.preventDefault(); moveFocus(Math.min(index + 1, rows.length - 1)); }
            if (event.key === "ArrowUp") { event.preventDefault(); moveFocus(Math.max(index - 1, 0)); }
            if (event.key === "Home") { event.preventDefault(); moveFocus(0); }
            if (event.key === "End") { event.preventDefault(); moveFocus(rows.length - 1); }
          }}
          role="treeitem"
          style={{ "--tree-depth": unit.depth } as CSSProperties}
          type="button"
        >
          <span>{unit.kind === "TEAM" ? <UsersRound aria-hidden="true" size={16} /> : <GitBranch aria-hidden="true" size={16} />}</span>
          <span><strong>{unit.name}</strong><small>{unit.code} · {unit.kind.replace("_", " ").toLowerCase()}</small></span>
          <em>{unitState(unit)}</em>
        </button>
      ))}
    </div>
  );
}
