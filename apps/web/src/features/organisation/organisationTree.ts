import type { OrganisationUnit } from "../../lib/api/types";

export type OrganisationTreeNode = OrganisationUnit & {
  children: OrganisationTreeNode[];
};

export function buildOrganisationTree(
  units: OrganisationUnit[],
): OrganisationTreeNode[] {
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
