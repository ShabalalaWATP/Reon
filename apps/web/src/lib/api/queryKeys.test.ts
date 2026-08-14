import { describe, expect, it } from "vitest";

import { protectedQueryKeys } from "./queryKeys";

describe("protected work-item query keys", () => {
  it("keeps list and paged cache shapes distinct at every scope", () => {
    expect(protectedQueryKeys.workItems("user-1")).toEqual([
      "protected", "user-1", "work-items",
    ]);
    expect(protectedQueryKeys.workItems("user-1", "unit-1")).toEqual([
      "protected", "user-1", "work-items", "unit", "unit-1",
    ]);
    expect(protectedQueryKeys.workItems("user-1", "unit-1", "request-1")).toEqual([
      "protected", "user-1", "work-items", "request", "request-1",
    ]);
    expect(protectedQueryKeys.workItemPages("user-1")).toEqual([
      "protected", "user-1", "work-items", "pages",
    ]);
    expect(protectedQueryKeys.workItemPages("user-1", "unit-1")).toEqual([
      "protected", "user-1", "work-items", "unit", "unit-1", "pages",
    ]);
    expect(protectedQueryKeys.workItemPages("user-1", "unit-1", "request-1")).toEqual([
      "protected", "user-1", "work-items", "request", "request-1", "pages",
    ]);
  });
});
