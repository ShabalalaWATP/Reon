class IncompatiblePayloadError extends Error {
  constructor(readonly payload: string) {
    super(`The server returned an incompatible ${payload}.`);
    this.name = "IncompatiblePayloadError";
  }
}

/**
 * Builds the optional `parse` hook that apiRequest applies to a response body,
 * so a payload that no longer matches the contract fails at the boundary
 * rather than reaching a component as a wrongly typed value. Checks are
 * hand-rolled rather than schema-library-based so the eager API layer adds
 * nothing to the initial bundle.
 */
export function payloadParser<Value>(payload: string, isCompatible: (value: unknown) => boolean) {
  return (value: unknown): Value => {
    if (!isCompatible(value)) throw new IncompatiblePayloadError(payload);
    return value as Value;
  };
}

export type Check = (value: unknown) => boolean;

export const isString: Check = (value) => typeof value === "string";
export const isNumber: Check = (value) => typeof value === "number" && Number.isFinite(value);
export const isBoolean: Check = (value) => typeof value === "boolean";

export function isOneOf(options: readonly string[]): Check {
  return (value) => typeof value === "string" && options.includes(value);
}

export function nullOr(check: Check): Check {
  return (value) => value === null || check(value);
}

export function optional(check: Check): Check {
  return (value) => value === undefined || check(value);
}

export function arrayOf(check: Check): Check {
  return (value) => Array.isArray(value) && value.every(check);
}

export function shape(fields: Record<string, Check>): Check {
  return (value) => {
    if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
    const record = value as Record<string, unknown>;
    return Object.entries(fields).every(([field, check]) => check(record[field]));
  };
}
