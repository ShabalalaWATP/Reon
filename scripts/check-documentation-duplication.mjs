import { readdir, readFile } from "node:fs/promises";
import { extname, join, relative } from "node:path";

const root = process.cwd();
const docsRoot = join(root, "docs");
const prose = new Map();
const userRows = [];
const failures = [];

function display(path) {
  return relative(root, path).replaceAll("\\", "/");
}

async function markdownFiles(path) {
  const files = [];
  for (const entry of await readdir(path, { withFileTypes: true })) {
    const next = join(path, entry.name);
    if (entry.isDirectory()) files.push(...(await markdownFiles(next)));
    else if (extname(entry.name) === ".md") files.push(next);
  }
  return files;
}

function normaliseParagraph(value) {
  return value.trim().replaceAll(/\s+/gu, " ");
}

function isComparableProse(value) {
  return (
    value.length >= 240 &&
    !value.startsWith("|") &&
    !value.startsWith("```") &&
    !value.startsWith("<!--")
  );
}

for (const path of await markdownFiles(docsRoot)) {
  const contents = await readFile(path, "utf8");
  for (const line of contents.split(/\r\n|\n|\r/gu)) {
    if (/^\| `admin\d+` \|/u.test(line)) userRows.push(display(path));
  }
  for (const paragraph of contents.split(/(?:\r?\n){2,}/gu)) {
    const normalised = normaliseParagraph(paragraph);
    if (!isComparableProse(normalised)) continue;
    const paths = prose.get(normalised) ?? [];
    paths.push(display(path));
    prose.set(normalised, paths);
  }
}

for (const [paragraph, paths] of prose) {
  const distinct = [...new Set(paths)];
  if (distinct.length > 1) {
    failures.push(
      `Repeated long-form prose in ${distinct.join(", ")}: ${paragraph.slice(0, 100)}…`,
    );
  }
}

const rosterAuthorities = [...new Set(userRows)];
if (
  rosterAuthorities.length !== 1 ||
  rosterAuthorities[0] !== "docs/architecture/ORGANISATION_AND_ROUTING.md"
) {
  failures.push(
    "The full mock-user roster must appear only in " +
      "docs/architecture/ORGANISATION_AND_ROUTING.md; found " +
      `${rosterAuthorities.join(", ") || "none"}.`,
  );
}

if (failures.length > 0) {
  console.error(`Documentation duplication gate failed:\n${failures.join("\n")}`);
  process.exit(1);
}

console.log("Documentation duplication gate passed.");
