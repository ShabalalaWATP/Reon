import { describe, expect, it } from "vitest";

import { isNavigationItemActive } from "./routes";

describe("primary navigation state", () => {
  it.each([
    ["/requests", "/requests", true],
    ["/requests/request-1", "/requests", true],
    ["/requests/new", "/requests", false],
    ["/requests/new", "/requests/new", true],
    ["/admin/users/user-1", "/admin/users", true],
    ["/tracking", "/triage", false],
  ])("matches %s against %s", (pathname, path, expected) => {
    expect(isNavigationItemActive(pathname, path)).toBe(expected);
  });
});
