import { describe, expect, it } from "vitest";

import type { ProtectedQueryScope } from "./queryKeys";
import { protectedQueryKeys } from "./queryKeys";

const staffScope: ProtectedQueryScope = {
  activeContext: "STAFF",
  contextVersion: 7,
  userId: "user-1",
};

describe("protected query keys", () => {
  it("captures identity context and version in every key", () => {
    const keys = protectedQueryKeys(staffScope);

    expect(keys.requests()).toEqual(["protected", "user-1", "STAFF", 7, "requests"]);
    expect(keys.conversations("request-1")).toEqual([
      "protected",
      "user-1",
      "STAFF",
      7,
      "request-conversations",
      "request-1",
    ]);
  });

  it("isolates the same user across contexts and context versions", () => {
    const staff = protectedQueryKeys(staffScope).requests();
    const customer = protectedQueryKeys({
      ...staffScope,
      activeContext: "CUSTOMER",
      contextVersion: 8,
    }).requests();
    const nextStaff = protectedQueryKeys({
      ...staffScope,
      contextVersion: 9,
    }).requests();

    expect(staff).not.toEqual(customer);
    expect(staff).not.toEqual(nextStaff);
  });

  it("keeps list and paged work-item cache shapes distinct", () => {
    const keys = protectedQueryKeys(staffScope);

    expect(keys.workItems()).toEqual(["protected", "user-1", "STAFF", 7, "work-items"]);
    expect(keys.workItems("unit-1")).toEqual([
      "protected",
      "user-1",
      "STAFF",
      7,
      "work-items",
      "unit",
      "unit-1",
    ]);
    expect(keys.workItems("unit-1", "request-1")).toEqual([
      "protected",
      "user-1",
      "STAFF",
      7,
      "work-items",
      "request",
      "request-1",
    ]);
    expect(keys.workItemPages()).toEqual([
      "protected",
      "user-1",
      "STAFF",
      7,
      "work-items",
      "pages",
    ]);
    expect(keys.workItemPages("unit-1")).toEqual([
      "protected",
      "user-1",
      "STAFF",
      7,
      "work-items",
      "unit",
      "unit-1",
      "pages",
    ]);
    expect(keys.workItemPages("unit-1", "request-1")).toEqual([
      "protected",
      "user-1",
      "STAFF",
      7,
      "work-items",
      "request",
      "request-1",
      "pages",
    ]);
  });
});
