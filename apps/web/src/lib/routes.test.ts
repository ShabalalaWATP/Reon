import { describe, expect, it } from "vitest";

import { documentTitleForRoute, isNavigationItemActive, memberLabel } from "./routes";

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

describe("route document titles", () => {
  it.each([
    ["/login", "Sign in · Mist Service"],
    ["/overview", "Home · Mist Service"],
    ["/my-work", "My assigned actions · Mist Service"],
    ["/profile", "Profile · Mist Service"],
    ["/notifications", "Notifications · Mist Service"],
    ["/organisation", "Organisation directory · Mist Service"],
    ["/calendar/month", "Personal calendar · Mist Service"],
    ["/statistics", "Operational statistics · Mist Service"],
    ["/teams/team-1/people/member-1", "Team member profile · Mist Service"],
    ["/teams/team-1/overview", "Team workspace · Mist Service"],
    ["/admin/users/new", "New user account · Mist Service"],
    ["/admin/users/user-1", "User accounts · Mist Service"],
    ["/admin/configuration", "Configuration · Mist Service"],
    ["/product-packages/new", "Product package · Mist Service"],
    ["/tracking", "Request tracking · Mist Service"],
    ["/tracking/request-1", "Tracked request · Mist Service"],
    ["/triage", "JIOC routing queue · Mist Service"],
    ["/coordination", "Incoming requests · Mist Service"],
    ["/allocation", "Ops routing queue · Mist Service"],
    ["/delivery/team", "Team work queue · Mist Service"],
    ["/delivery/my-work", "Production queue · Mist Service"],
    ["/quality-release", "QC Team queue · Mist Service"],
    ["/requests", "My requests · Mist Service"],
    ["/requests/new", "New request · Mist Service"],
    ["/requests/drafts/draft-1", "Request draft · Mist Service"],
    ["/requests/request-1", "Request detail · Mist Service"],
    ["/", "Mist Service"],
    ["/unknown/page", "Mist Service"],
  ])("names %s", (pathname, expected) => {
    expect(documentTitleForRoute(pathname)).toBe(expected);
  });
});

describe("member labels", () => {
  it("names QC people by workspace position because one role spans two positions", () => {
    expect(memberLabel("QUALITY_RELEASE", "MEMBER")).toBe("QC User");
    expect(memberLabel("QUALITY_RELEASE", "MANAGER")).toBe("QC Manager");
    expect(memberLabel("QUALITY_RELEASE", undefined)).toBe("Combined QC Team");
    expect(memberLabel("QUALITY_RELEASE", null)).toBe("Combined QC Team");
  });

  it("leaves every other role on its representative label regardless of position", () => {
    expect(memberLabel("DELIVERY_SPECIALIST", "MEMBER")).toBe("Team Analyst");
    expect(memberLabel("DELIVERY_TEAM_LEAD", "MANAGER")).toBe("Team Manager");
    expect(memberLabel("INTAKE_TRIAGE", "MEMBER")).toBe("JIOC Routing User");
  });
});
