import { ChevronRight } from "lucide-react";

import type { ConfigurationEdgeDraft, ConfigurationUnitDraft } from "../../lib/api/configurationTypes";
import { configurationPath } from "./configurationModel";

export function ConfigurationBreadcrumbs({
  edges,
  effectiveAt,
  onSelect,
  selectedId,
  units,
}: {
  edges: ConfigurationEdgeDraft[];
  effectiveAt: string;
  onSelect: (unitId: string) => void;
  selectedId: string | null;
  units: ConfigurationUnitDraft[];
}) {
  const path = configurationPath(units, edges, selectedId, effectiveAt);
  if (!path.length) return <p className="configuration-breadcrumb-empty">Select a unit to see its organisational path.</p>;
  return <nav aria-label="Selected organisation path" className="configuration-breadcrumbs"><ol>{path.map((unit, index) => <li key={unit.unitId}>{index ? <ChevronRight aria-hidden="true" size={14} /> : null}<button aria-current={unit.unitId === selectedId ? "location" : undefined} onClick={() => onSelect(unit.unitId)} type="button">{unit.name} · {unit.code}</button></li>)}</ol></nav>;
}
