import type { AccountContext, Session, User, UserRole } from "../api/types";

const USER_ROLES: ReadonlySet<string> = new Set([
  "PLATFORM_ADMIN",
  "REQUESTER",
  "INTAKE_TRIAGE",
  "SERVICE_COORDINATION",
  "OPERATIONS_ALLOCATION",
  "DELIVERY_TEAM_LEAD",
  "DELIVERY_SPECIALIST",
  "QUALITY_RELEASE",
]);
const ACCOUNT_CONTEXTS: ReadonlySet<string> = new Set(["CUSTOMER", "STAFF"]);

class IncompatibleSessionError extends Error {
  constructor() {
    super("The server returned an incompatible session.");
    this.name = "IncompatibleSessionError";
  }
}

export function requireCompatibleSession(value: unknown): Session {
  if (!isRecord(value) || !isRecord(value.user)) throw new IncompatibleSessionError();
  const user = compatibleUser(value.user);
  const activeContext = accountContext(value.activeContext);
  const availableContexts = contextList(value.availableContexts);
  if (!availableContexts.includes(activeContext)) throw new IncompatibleSessionError();
  return {
    user,
    csrfToken: requiredString(value.csrfToken),
    expiresAt: requiredDate(value.expiresAt),
    idleExpiresAt: optionalDate(value.idleExpiresAt),
    idleTimeoutSeconds: optionalPositiveInteger(value.idleTimeoutSeconds),
    elevatedUntil: nullableDate(value.elevatedUntil),
    activeContext,
    availableContexts,
    contextVersion: nonNegativeInteger(value.contextVersion),
  };
}

function compatibleUser(value: Record<string, unknown>): User {
  const role = requiredString(value.role);
  if (!USER_ROLES.has(role)) throw new IncompatibleSessionError();
  return {
    id: requiredString(value.id),
    username: requiredString(value.username),
    displayName: requiredString(value.displayName),
    role: role as UserRole,
    scope: requiredString(value.scope),
    organisationUnitIds: stringList(value.organisationUnitIds),
  };
}

function accountContext(value: unknown): AccountContext {
  const context = requiredString(value);
  if (!ACCOUNT_CONTEXTS.has(context)) throw new IncompatibleSessionError();
  return context as AccountContext;
}

function contextList(value: unknown): AccountContext[] {
  const contexts = stringList(value);
  if (contexts.length === 0 || contexts.some((item) => !ACCOUNT_CONTEXTS.has(item))) {
    throw new IncompatibleSessionError();
  }
  return [...new Set(contexts)] as AccountContext[];
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string")) {
    throw new IncompatibleSessionError();
  }
  return value;
}

function requiredString(value: unknown): string {
  if (typeof value !== "string" || value.trim() === "") {
    throw new IncompatibleSessionError();
  }
  return value;
}

function requiredDate(value: unknown): string {
  const date = requiredString(value);
  if (Number.isNaN(Date.parse(date))) throw new IncompatibleSessionError();
  return date;
}

function optionalDate(value: unknown): string | undefined {
  return value === undefined ? undefined : requiredDate(value);
}

function nullableDate(value: unknown): string | null {
  return value === null ? null : requiredDate(value);
}

function optionalPositiveInteger(value: unknown): number | undefined {
  if (value === undefined) return undefined;
  if (!Number.isInteger(value) || Number(value) <= 0) throw new IncompatibleSessionError();
  return Number(value);
}

function nonNegativeInteger(value: unknown): number {
  if (!Number.isInteger(value) || Number(value) < 0) throw new IncompatibleSessionError();
  return Number(value);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
