import { z } from "zod";

class IncompatiblePayloadError extends Error {
  constructor(readonly payload: string) {
    super(`The server returned an incompatible ${payload}.`);
    this.name = "IncompatiblePayloadError";
  }
}

/**
 * Builds the optional `parse` hook that apiRequest applies to a response body,
 * so a payload that no longer matches the contract fails at the boundary rather
 * than reaching a component as a wrongly typed value.
 */
export function payloadParser<Value>(payload: string, schema: z.ZodType<Value>) {
  return (value: unknown): Value => {
    const parsed = schema.safeParse(value);
    if (!parsed.success) throw new IncompatiblePayloadError(payload);
    return parsed.data;
  };
}
