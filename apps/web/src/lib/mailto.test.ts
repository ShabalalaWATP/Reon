import { describe, expect, it } from "vitest";

import { mailtoHref } from "./mailto";

describe("mailto links", () => {
  it("preserves the address separator while encoding URI controls", () => {
    expect(mailtoHref("customer+tag@example.test")).toBe("mailto:customer%2Btag@example.test");
    expect(mailtoHref("customer@example.test?bcc=attacker%40example.test")).toBe(
      "mailto:customer@example.test%3Fbcc%3Dattacker%2540example.test",
    );
    expect(mailtoHref("customer@example.test?bcc=attacker@example.test")).toBe(
      "mailto:customer%40example.test%3Fbcc%3Dattacker%40example.test",
    );
  });
});
