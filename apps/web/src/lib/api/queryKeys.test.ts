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

  it("keeps flat and paged action cache shapes distinct for every filter key", () => {
    const keys = protectedQueryKeys(staffScope);
    const filterKeys = ["", "overview", "quality-overview", "pages", '{"sections":[]}'];
    const flat = filterKeys.map((filters) => keys.actions(filters));
    const paged = filterKeys.map((filters) => keys.actionPages(filters));

    expect(keys.actions("overview")).toEqual([
      "protected",
      "user-1",
      "STAFF",
      7,
      "my-actions",
      "overview",
    ]);
    expect(keys.actionPages("overview")).toEqual([
      "protected",
      "user-1",
      "STAFF",
      7,
      "my-actions",
      "overview",
      "pages",
    ]);
    // A flat key can never reach the paged length, so no filter string can make the two collide.
    for (const pagedKey of paged) {
      for (const flatKey of flat) expect(pagedKey).not.toEqual(flatKey);
    }
    const rootKey = [...keys.actionsRoot()];
    for (const key of [...flat, ...paged]) {
      expect(key.slice(0, rootKey.length)).toEqual(rootKey);
    }
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
