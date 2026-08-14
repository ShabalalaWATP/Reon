export type Identified = { id: string };

export function flattenUniquePages<T extends Identified>(pages: ReadonlyArray<{ items: T[] }>) {
  const items = new Map<string, T>();
  pages.forEach((page) => {
    page.items.forEach((item) => items.set(item.id, item));
  });
  return [...items.values()];
}
