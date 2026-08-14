import type { StatisticsScope, StatisticsUnit } from "../../lib/api/statisticsTypes";

export function StatisticsHierarchy({
  scope,
  selectedUnitId,
  breadcrumb,
  onSelect,
}: {
  scope: StatisticsScope;
  selectedUnitId: string;
  breadcrumb: StatisticsUnit[];
  onSelect: (unitId: string) => void;
}) {
  return (
    <div className="statistics-hierarchy">
      <label className="form-field">
        Organisation
        <select onChange={(event) => onSelect(event.target.value)} value={selectedUnitId}>
          {scope.units.map((unit) => (
            <option key={unit.id} value={unit.id}>
              {`${"  ".repeat(unit.depth)}${unit.name}`}
            </option>
          ))}
        </select>
      </label>
      <nav aria-label="Statistics organisation breadcrumb" className="statistics-breadcrumb">
        {breadcrumb.map((unit, index) => (
          <span key={unit.id}>
            {index > 0 ? <i aria-hidden="true">/</i> : null}
            <button
              aria-current={unit.id === selectedUnitId ? "page" : undefined}
              disabled={unit.id === selectedUnitId}
              onClick={() => onSelect(unit.id)}
              type="button"
            >
              {unit.name}
            </button>
          </span>
        ))}
      </nav>
    </div>
  );
}
