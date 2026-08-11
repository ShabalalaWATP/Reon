import type { RelatedRecordMatch } from "../../lib/api/types";

export function comparisonSummary(
  query: string,
  pending: boolean,
  error: boolean,
  items?: ReadonlyArray<Pick<RelatedRecordMatch, "matchBand">>,
): string {
  if (pending) return "Checking authorised request history…";
  if (error) return "Comparison unavailable";
  if (!items) return "No comparison available";
  if (query) return items.length === 1 ? `1 result for “${query}”` : `${items.length} results for “${query}”`;
  if (items.length === 0) return "No credible matches found";
  const strong = items.filter((item) => item.matchBand === "STRONG").length;
  if (strong === 0) return `No strong matches · ${items.length} lower-confidence ${items.length === 1 ? "suggestion" : "suggestions"}`;
  const other = items.length - strong;
  const strongLabel = `${strong} strong ${strong === 1 ? "match" : "matches"}`;
  return other ? `${strongLabel} · ${other} other ${other === 1 ? "suggestion" : "suggestions"}` : strongLabel;
}
