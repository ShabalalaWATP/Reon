import type {
  BoardFilters,
  BoardMoveInput,
  BoardResult,
  Iteration,
  ReservationInput,
  SavedBoardView,
  WorkPackage,
  WorkPackageInput,
  WorkPackageStatus,
} from "./boardTypes";
import { apiRequest } from "./client";

const teamPath = (teamId: string) => `/team-workspaces/${encodeURIComponent(teamId)}`;

export const boardApi = {
  board: (
    teamId: string,
    filters: Partial<BoardFilters> = {},
    page: { cursor?: string | null; limit?: number } = {},
  ) => {
    const query = new URLSearchParams();
    if (filters.search) query.set("search", filters.search);
    filters.columns?.forEach((value) => query.append("column", value));
    filters.priorities?.forEach((value) => query.append("priority", value));
    filters.itemTypes?.forEach((value) => query.append("itemType", value));
    if (filters.ownerUserId) query.set("ownerId", filters.ownerUserId);
    if (filters.dueBefore) query.set("dueBefore", filters.dueBefore);
    if (page.cursor) query.set("cursor", page.cursor);
    if (page.limit) query.set("limit", String(page.limit));
    return apiRequest<BoardResult>(`${teamPath(teamId)}/board${query.size ? `?${query}` : ""}`);
  },
  moveItem: (teamId: string, input: BoardMoveInput, csrfToken: string) =>
    apiRequest<WorkPackage>(`${teamPath(teamId)}/board/moves`, { body: input, csrfToken, method: "POST" }),
  configure: (teamId: string, input: { grantId: string; expectedVersion: number; wipLimits: Record<string, number> }, csrfToken: string) =>
    apiRequest<{ wipLimits: Record<string, number>; version: number }>(`${teamPath(teamId)}/board/configuration`, { body: input, csrfToken, method: "PUT" }),
  createView: (teamId: string, input: { name: string; filters: BoardFilters }, csrfToken: string) =>
    apiRequest<SavedBoardView>(`${teamPath(teamId)}/board/saved-views`, { body: input, csrfToken, method: "POST" }),
  updateView: (teamId: string, viewId: string, input: { name: string; filters: BoardFilters; expectedVersion: number }, csrfToken: string) =>
    apiRequest<SavedBoardView>(`${teamPath(teamId)}/board/saved-views/${encodeURIComponent(viewId)}`, { body: input, csrfToken, method: "PUT" }),
  deleteView: (teamId: string, viewId: string, expectedVersion: number, csrfToken: string) =>
    apiRequest<void>(`${teamPath(teamId)}/board/saved-views/${encodeURIComponent(viewId)}`, { body: { expectedVersion }, csrfToken, method: "DELETE" }),
  packages: (teamId: string) => apiRequest<{ items: WorkPackage[] }>(`${teamPath(teamId)}/packages`),
  package: (teamId: string, packageId: string) => apiRequest<WorkPackage>(`${teamPath(teamId)}/packages/${encodeURIComponent(packageId)}`),
  createPackage: (teamId: string, input: WorkPackageInput, csrfToken: string) =>
    apiRequest<WorkPackage>(`${teamPath(teamId)}/packages`, { body: input, csrfToken, method: "POST" }),
  updatePackage: (teamId: string, packageId: string, input: WorkPackageInput & { expectedVersion: number }, csrfToken: string) =>
    apiRequest<WorkPackage>(`${teamPath(teamId)}/packages/${encodeURIComponent(packageId)}`, { body: input, csrfToken, method: "PUT" }),
  movePackage: (teamId: string, packageId: string, input: { grantId: string | null; expectedVersion: number; target: WorkPackageStatus; reason: string }, csrfToken: string) =>
    apiRequest<WorkPackage>(`${teamPath(teamId)}/packages/${encodeURIComponent(packageId)}/move`, { body: input, csrfToken, method: "POST" }),
  reserve: (teamId: string, packageId: string, packageVersion: number, input: ReservationInput, csrfToken: string) =>
    apiRequest<WorkPackage>(`${teamPath(teamId)}/packages/${encodeURIComponent(packageId)}/reservations?packageVersion=${packageVersion}`, { body: input, csrfToken, method: "POST" }),
  cancelReservation: (teamId: string, packageId: string, reservationId: string, packageVersion: number, input: { grantId: string | null; expectedVersion: number; reason: string }, csrfToken: string) =>
    apiRequest<WorkPackage>(`${teamPath(teamId)}/packages/${encodeURIComponent(packageId)}/reservations/${encodeURIComponent(reservationId)}/cancel?packageVersion=${packageVersion}`, { body: input, csrfToken, method: "POST" }),
  iterations: (teamId: string) => apiRequest<{ items: Iteration[] }>(`${teamPath(teamId)}/iterations`),
  createIteration: (teamId: string, input: { grantId: string; name: string; goal: string; startsOn: string; endsOn: string }, csrfToken: string) =>
    apiRequest<Iteration>(`${teamPath(teamId)}/iterations`, { body: input, csrfToken, method: "POST" }),
  closeIteration: (teamId: string, iterationId: string, input: { grantId: string; expectedVersion: number; completionSummary: string }, csrfToken: string) =>
    apiRequest<Iteration>(`${teamPath(teamId)}/iterations/${encodeURIComponent(iterationId)}/close`, { body: input, csrfToken, method: "POST" }),
};
