import { describe, expect, it } from "vitest";

import { json, mockFetch } from "../../test/render";
import { workApi } from "./workClient";

describe("work API compatibility calls", () => {
  it("preserves the caller mutation ID for coordination retries", async () => {
    let body: string | undefined;
    mockFetch((_url, init) => {
      body = init.body?.toString();
      return json({ event: {} });
    });

    await workApi.postRequestCoordination(
      "request-id",
      {
        audience: "CUSTOMER",
        body: "Please confirm the synthetic priority.",
        clientMutationId: "99999999-9999-4999-8999-999999999999",
      },
      "csrf-token",
    );

    expect(JSON.parse(body ?? "{}")).toEqual({
      audience: "CUSTOMER",
      body: "Please confirm the synthetic priority.",
      clientMutationId: "99999999-9999-4999-8999-999999999999",
    });
  });
});
