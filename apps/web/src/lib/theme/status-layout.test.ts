import { readFileSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { describe, expect, it } from "vitest";

const base = readFileSync(
  path.resolve(process.cwd(), "src/styles/base.css"),
  "utf8",
);

describe("status label layout", () => {
  it("allows long workflow labels to wrap inside their column", () => {
    const rule = base.match(/\.status-pill \{[^}]+\}/u)?.[0] ?? "";

    expect(rule).toContain("width: fit-content");
    expect(rule).toContain("max-width: 100%");
    expect(rule).toContain("overflow-wrap: anywhere");
    expect(rule).toContain("white-space: normal");
  });

  it("keeps the status marker from shrinking when the label wraps", () => {
    const rule = base.match(/\.status-pill::before \{[^}]+\}/u)?.[0] ?? "";

    expect(rule).toContain("flex: 0 0 auto");
  });
});
