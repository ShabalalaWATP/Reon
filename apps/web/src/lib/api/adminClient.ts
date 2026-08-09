import type {
  AdminUser,
  AdminUserStatusInput,
  AdminUserUpdateInput,
  AdminUserWriteInput,
  ListResponse,
  OrganisationUnit,
  OrganisationUnitRenameInput,
} from "./types";
import { apiRequest, pagedPath } from "./transport";

export const adminApi = {
  adminUsers: (query = "", cursor?: string) =>
    apiRequest<ListResponse<AdminUser>>(
      pagedPath("/admin/users", cursor, query ? { query } : {}),
    ),
  adminUser: (id: string) =>
    apiRequest<AdminUser>(`/admin/users/${encodeURIComponent(id)}`),
  createAdminUser: (input: AdminUserWriteInput, csrfToken: string) =>
    apiRequest<AdminUser>("/admin/users", {
      body: input,
      csrfToken,
      method: "POST",
    }),
  updateAdminUser: (
    id: string,
    input: AdminUserUpdateInput,
    csrfToken: string,
  ) => apiRequest<AdminUser>(`/admin/users/${encodeURIComponent(id)}`, {
    body: input,
    csrfToken,
    method: "PATCH",
  }),
  updateAdminUserStatus: (
    id: string,
    input: AdminUserStatusInput,
    csrfToken: string,
  ) => apiRequest<AdminUser>(`/admin/users/${encodeURIComponent(id)}/status`, {
    body: input,
    csrfToken,
    method: "PATCH",
  }),
  renameOrganisationUnit: (
    id: string,
    input: OrganisationUnitRenameInput,
    csrfToken: string,
  ) => apiRequest<OrganisationUnit>(
    `/admin/organisation/units/${encodeURIComponent(id)}`,
    { body: input, csrfToken, method: "PATCH" },
  ),
};
