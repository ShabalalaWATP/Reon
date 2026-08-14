export type UserRole =
  | "PLATFORM_ADMIN"
  | "REQUESTER"
  | "INTAKE_TRIAGE"
  | "SERVICE_COORDINATION"
  | "OPERATIONS_ALLOCATION"
  | "DELIVERY_TEAM_LEAD"
  | "DELIVERY_SPECIALIST"
  | "QUALITY_RELEASE";

export type AccountContext = "CUSTOMER" | "STAFF";

export type User = {
  id: string;
  username: string;
  displayName: string;
  role: UserRole;
  scope: string;
  organisationUnitIds: string[];
};

export type Session = {
  user: User;
  csrfToken: string;
  expiresAt: string;
  idleExpiresAt?: string;
  idleTimeoutSeconds?: number;
  elevatedUntil: string | null;
  activeContext: AccountContext;
  availableContexts: AccountContext[];
  contextVersion: number;
};

export type PersonalProfile = {
  userId: string;
  name: string;
  username: string;
  email: string;
  role: UserRole;
  profileTeam: string | null;
  rankOrGrade: string | null;
  serviceNumber: string | null;
  additionalInformation: string | null;
  skills: string[];
  version: number;
};

export type PersonalProfileUpdate = Pick<
  PersonalProfile,
  "profileTeam" | "rankOrGrade" | "serviceNumber" | "additionalInformation" | "skills"
> & { expectedVersion: number };

export type ListResponse<T> = {
  items: T[];
  nextCursor?: string | null;
};
