export type UserRole =
  | "PLATFORM_ADMIN"
  | "REQUESTER"
  | "INTAKE_TRIAGE"
  | "SERVICE_COORDINATION"
  | "OPERATIONS_ALLOCATION"
  | "DELIVERY_TEAM_LEAD"
  | "DELIVERY_SPECIALIST"
  | "QUALITY_RELEASE";

export type User = {
  id: string;
  username: string;
  displayName: string;
  role: UserRole;
  scope: string;
};

export type Session = {
  user: User;
  csrfToken: string;
  expiresAt: string;
  elevatedUntil: string | null;
};

export type ListResponse<T> = {
  items: T[];
  nextCursor?: string | null;
};
