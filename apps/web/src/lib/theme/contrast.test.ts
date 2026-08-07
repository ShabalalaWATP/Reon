import { readFileSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { describe, expect, it } from "vitest";

const tokens = readFileSync(
  path.resolve(process.cwd(), "src/styles/tokens.css"),
  "utf8",
);
const base = readFileSync(
  path.resolve(process.cwd(), "src/styles/base.css"),
  "utf8",
);
const [darkTokens, lightTokens = ""] = tokens.split(
  ':root[data-theme="light"]',
);

function token(block: string, name: string) {
  const match = block.match(new RegExp(`--${name}:\\s*(#[0-9a-f]{6})`, "i"));
  if (!match) throw new Error(`Missing colour token --${name}.`);
  return match[1];
}

function relativeLuminance(hex: string) {
  const channels = hex
    .slice(1)
    .match(/.{2}/g)!
    .map((value) => Number.parseInt(value, 16) / 255)
    .map((value) =>
      value <= 0.04045
        ? value / 12.92
        : ((value + 0.055) / 1.055) ** 2.4,
    );
  return (
    0.2126 * channels[0] +
    0.7152 * channels[1] +
    0.0722 * channels[2]
  );
}

function whiteContrast(hex: string) {
  return 1.05 / (relativeLuminance(hex) + 0.05);
}

describe("primary action contrast", () => {
  it.each([
    ["dark", darkTokens],
    ["light", lightTokens],
  ])("keeps %s primary and hover colours at WCAG AA", (_theme, block) => {
    expect(whiteContrast(token(block, "accent-strong"))).toBeGreaterThanOrEqual(
      4.5,
    );
    expect(
      whiteContrast(token(block, "accent-strong-hover")),
    ).toBeGreaterThanOrEqual(4.5);
  });

  it("uses the checked hover token for primary buttons", () => {
    expect(base).toContain(
      ".button--primary:hover:not(:disabled) { background: var(--accent-strong-hover); }",
    );
  });
});
