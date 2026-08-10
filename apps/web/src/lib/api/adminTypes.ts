import type { User, UserRole } from "./coreTypes";
import type { OrganisationUnit } from "./organisationTypes";

export type UserMembership = {
  organisationUnitId: string;
  organisationUnitName: string;
  organisationUnitKind: OrganisationUnit["kind"];
  workspacePosition: "MANAGER" | "MEMBER";
};

export type AdminUser = Omit<User, "organisationUnitIds"> & {
  email: string;
  isActive: boolean;
  version: number;
  memberships: UserMembership[];
  createdAt: string;
  updatedAt: string;
};

export type AdminUserWriteInput = {
  displayName: string;
  email: string;
  role: UserRole;
  scope: string;
  organisationUnitIds: string[];
  workspacePosition?: "MANAGER" | "MEMBER" | null;
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

export type AccountRequest = {
  id: string;
  displayName: string;
  contactEmail: string;
  reason: string;
  status: "PENDING" | "APPROVED" | "REJECTED";
  decisionNote: string | null;
  createdUserId: string | null;
  version: number;
  createdAt: string;
  updatedAt: string;
  reviewedAt: string | null;
};
