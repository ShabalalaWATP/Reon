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
const classification = readFileSync(
  path.resolve(process.cwd(), "src/styles/classification.css"),
  "utf8",
);
const [darkTokens, lightTokens = ""] = tokens.split(
  ':root[data-theme="light"]',
);

function token(block: string, name: string) {
  const prefix = `--${name}:`;
  const declaration = block
    .split(";")
    .map((value) => value.trim())
    .find((value) => value.startsWith(prefix));
  const value = declaration?.slice(prefix.length).trim();
  if (!value || !/^#(?:[0-9a-f]{3}|[0-9a-f]{6})$/iu.test(value)) {
    throw new Error(`Missing colour token --${name}.`);
  }
  return value;
}

function relativeLuminance(hex: string) {
  const normalised = hex.length === 4
    ? `#${[...hex.slice(1)].map((value) => value.repeat(2)).join("")}`
    : hex;
  const channels = normalised
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

function contrast(first: string, second: string) {
  const firstLuminance = relativeLuminance(first);
  const secondLuminance = relativeLuminance(second);
  return (
    (Math.max(firstLuminance, secondLuminance) + 0.05)
    / (Math.min(firstLuminance, secondLuminance) + 0.05)
  );
}

const surfaceTokens = ["bg", "surface", "surface-strong", "surface-muted", "surface-raised"];
const semanticTextTokens = ["text", "muted", "accent", "teal", "success", "warning", "critical"];

describe("primary action contrast", () => {
  it.each([
    ["dark", darkTokens],
    ["light", lightTokens],
  ])("keeps %s primary and hover colours at WCAG AA", (_theme, block) => {
    expect(contrast("#ffffff", token(block, "accent-strong"))).toBeGreaterThanOrEqual(
      4.5,
    );
    expect(
      contrast("#ffffff", token(block, "accent-strong-hover")),
    ).toBeGreaterThanOrEqual(4.5);
  });

  it.each([
    ["dark", darkTokens],
    ["light", lightTokens],
  ])("keeps %s semantic text colours readable on every core surface", (_theme, block) => {
    for (const foreground of semanticTextTokens) {
      for (const background of surfaceTokens) {
        expect(
          contrast(token(block, foreground), token(block, background)),
          `${foreground} on ${background}`,
        ).toBeGreaterThanOrEqual(4.5);
      }
    }
  });

  it.each([
    ["dark", darkTokens],
    ["light", lightTokens],
  ])("keeps %s strong control boundaries distinct", (_theme, block) => {
    for (const background of surfaceTokens) {
      expect(
        contrast(token(block, "border-strong"), token(block, background)),
        `border-strong on ${background}`,
      ).toBeGreaterThanOrEqual(3);
    }
  });

  it("uses the checked hover token for primary buttons", () => {
    expect(base).toContain(
      ".button--primary:hover:not(:disabled) { background: var(--accent-strong-hover); }",
    );
  });

  it("keeps every classification strip above normal-text contrast", () => {
    const backgrounds = [...classification.matchAll(/background:\s*(#[0-9a-f]{6})/giu)]
      .map((match) => match[1]);
    expect(backgrounds).toHaveLength(4);
    for (const background of backgrounds) {
      expect(contrast("#ffffff", background)).toBeGreaterThanOrEqual(4.5);
    }
  });
});
