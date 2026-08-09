import type { User, UserRole } from "./coreTypes";
import type { OrganisationUnit } from "./organisationTypes";

export type UserMembership = {
  organisationUnitId: string;
  organisationUnitName: string;
  organisationUnitKind: OrganisationUnit["kind"];
};

export type AdminUser = User & {
  isActive: boolean;
  version: number;
  memberships: UserMembership[];
  createdAt: string;
  updatedAt: string;
};

export type AdminUserWriteInput = {
  displayName: string;
  role: UserRole;
  scope: string;
  organisationUnitIds: string[];
};

export type AdminUserUpdateInput = AdminUserWriteInput & {
  expectedVersion: number;
};
export type AdminUserStatusInput = {
  isActive: boolean;
  expectedVersion: number;
};
export type OrganisationUnitRenameInput = {
  name: string;
  expectedVersion: number;
};
