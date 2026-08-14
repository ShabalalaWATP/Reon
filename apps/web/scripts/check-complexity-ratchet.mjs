/* global console, process */

import { relative, sep } from "node:path";

import { ESLint } from "eslint";

import { frontendComplexityDebt } from "./complexity-baseline.js";

const target = 12;
const eslint = new ESLint({
  overrideConfig: { rules: { complexity: ["error", 0] } },
});
const results = await eslint.lintFiles(["src/**/*.{ts,tsx}"]);
const actual = {};

for (const result of results) {
  const path = relative(process.cwd(), result.filePath).split(sep).join("/");
  if (path.includes(".test.") || path.startsWith("src/test/")) continue;
  const complexities = result.messages
    .filter((message) => message.ruleId === "complexity")
    .map((message) => {
      const match = /complexity of (\d+)/u.exec(message.message);
      if (!match) {
        throw new Error(`Cannot parse ESLint complexity: ${message.message}`);
      }
      return Number(match[1]);
    });
  const maximum = Math.max(0, ...complexities);
  if (maximum > target) actual[path] = maximum;
}

const actualNames = new Set(Object.keys(actual));
const baselineNames = new Set(Object.keys(frontendComplexityDebt));
const added = [...actualNames].filter((name) => !baselineNames.has(name)).sort();
const removed = [...baselineNames].filter((name) => !actualNames.has(name)).sort();
const changed = [...actualNames]
  .filter((name) => baselineNames.has(name) && actual[name] !== frontendComplexityDebt[name])
  .sort()
  .map((name) => `${name}: ${frontendComplexityDebt[name]} -> ${actual[name]}`);

if (added.length || removed.length || changed.length) {
  console.error("Frontend complexity debt changed.");
  if (added.length) console.error(`New debt: ${added.join(", ")}`);
  if (removed.length) console.error(`Remove remediated entries: ${removed.join(", ")}`);
  if (changed.length) {
    console.error(`Update reduced debt or reject growth: ${changed.join(", ")}`);
  }
  process.exit(1);
}

console.log(`Frontend complexity ratchet passed for ${actualNames.size} debt files.`);
