import type { OrganisationUnit } from "../../lib/api/types";

export type OrganisationTreeNode = OrganisationUnit & {
  children: OrganisationTreeNode[];
};

export function buildOrganisationTree(units: OrganisationUnit[]): OrganisationTreeNode[] {
  const nodes = new Map<string, OrganisationTreeNode>(
    units.map((unit) => [unit.id, { ...unit, children: [] }]),
  );
  const roots: OrganisationTreeNode[] = [];

  for (const unit of units) {
    const node = nodes.get(unit.id)!;
    const parent = unit.parentId ? nodes.get(unit.parentId) : undefined;
    if (parent && parent.id !== node.id) parent.children.push(node);
    else roots.push(node);
  }

  return roots;
}

/**
 * The viewer's place in the hierarchy.
 *
 * `own` is every unit the viewer belongs to. `path` is every unit on the way
 * down to any of them, so a branch can be lit from the root to the viewer.
 * `trail` is the ancestor chain for the first unit, root first, for a
 * breadcrumb. A viewer with no unit, such as a Customer, gets empty sets.
 */
export type ViewerPlacement = {
  own: ReadonlySet<string>;
  path: ReadonlySet<string>;
  trail: OrganisationUnit[];
};

export function locateViewer(
  units: OrganisationUnit[],
  unitIds: readonly string[],
): ViewerPlacement {
  const byId = new Map(units.map((unit) => [unit.id, unit]));
  const own = new Set(unitIds.filter((id) => byId.has(id)));
  const path = new Set<string>();
  const ancestors = (id: string): OrganisationUnit[] => {
    const chain: OrganisationUnit[] = [];
    let current = byId.get(id);
    while (current) {
      chain.unshift(current);
      current = current.parentId ? byId.get(current.parentId) : undefined;
    }
    return chain;
  };
  for (const id of own) {
    for (const unit of ancestors(id)) path.add(unit.id);
  }
  const first = [...own][0];
  return { own, path, trail: first ? ancestors(first) : [] };
}
