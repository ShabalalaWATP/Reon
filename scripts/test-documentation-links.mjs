import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import {
  pngValidationFailures,
  svgSafetyFailures,
} from "./asset-validation-support.mjs";
import { markdownAnchorIds } from "./markdown-anchor-support.mjs";

function pngChunk(type, data = Buffer.alloc(0)) {
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  return Buffer.concat([length, Buffer.from(type, "ascii"), data, Buffer.alloc(4)]);
}

const fixtureRoot = await mkdtemp(join(tmpdir(), "mist-documentation-links-"));
try {
  const fixture = join(fixtureRoot, "guide.md");
  await writeFile(
    fixture,
    [
      "# Current position, 18 August 2026",
      "## CUST-09: Maintain a personal profile",
      "## Repeated heading",
      "## Repeated heading",
      '<span id="explicit-anchor"></span>',
      "```markdown",
      "# Fenced example is not a heading",
      "```",
    ].join("\n"),
  );
  const anchors = markdownAnchorIds(await readFile(fixture, "utf8"));
  assert(anchors.has("current-position-18-august-2026"));
  assert(anchors.has("cust-09-maintain-a-personal-profile"));
  assert(anchors.has("repeated-heading"));
  assert(anchors.has("repeated-heading-1"));
  assert(anchors.has("explicit-anchor"));
  assert(!anchors.has("current-position-15-august-2026"));
  assert(!anchors.has("fenced-example-is-not-a-heading"));

  const header = Buffer.alloc(13);
  header.writeUInt32BE(1600, 0);
  header.writeUInt32BE(1000, 4);
  const validPngStructure = Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    pngChunk("IHDR", header),
    pngChunk("IDAT", Buffer.from([1])),
    pngChunk("IEND"),
  ]);
  assert.deepEqual(pngValidationFailures(validPngStructure, 1600, 1000), []);
  assert(pngValidationFailures(validPngStructure.subarray(0, 20), 1600, 1000).length > 0);
  assert(
    pngValidationFailures(
      Buffer.concat([
        Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
        pngChunk("IHDR", header),
        pngChunk("IEND"),
      ]),
      1600,
      1000,
    ).includes("PNG IDAT chunk is missing"),
  );

  const safeSvg = '<svg viewBox="0 0 1 1"><path d="M0 0"/></svg>';
  assert.deepEqual(svgSafetyFailures(safeSvg), []);
  for (const unsafeSvg of [
    '<svg viewBox="0 0 1 1" onload="alert(1)"/>',
    '<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]><svg viewBox="0 0 1 1"/>',
    '<svg viewBox="0 0 1 1"><style>@import url(https://example.test/a.css)</style></svg>',
    '<svg viewBox="0 0 1 1"><image href = "https://example.test/a.png"/></svg>',
    '<svg viewBox="0 0 1 1"><image href="data:image/svg+xml,a"/></svg>',
    '<svg viewBox="0 0 1 1"><image href="file:///tmp/a.png"/></svg>',
  ]) {
    assert(svgSafetyFailures(unsafeSvg).length > 0);
  }
} finally {
  await rm(fixtureRoot, { recursive: true, force: true });
}

console.log("Documentation fragment-link regression tests passed.");
