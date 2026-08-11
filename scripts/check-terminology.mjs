import { readdir, readFile, stat } from "node:fs/promises";
import { extname, join, relative, resolve, sep } from "node:path";

const repositoryRoot = process.cwd();
const roots = [
  "apps/api/src",
  "apps/api/tests",
  "apps/api/alembic",
  "apps/web",
  "scripts",
  "workflow",
];
const checked = new Set([
  ".bpmn",
  ".conf",
  ".css",
  ".html",
  ".ini",
  ".js",
  ".json",
  ".mako",
  ".mjs",
  ".ps1",
  ".py",
  ".sh",
  ".toml",
  ".ts",
  ".tsx",
  ".yaml",
  ".yml",
]);
const ignoredDirectories = new Set([
  ".data",
  "__pycache__",
  "coverage",
  "dist",
  "htmlcov",
  "node_modules",
  "playwright-report",
  "test-results",
]);
const ignoredFiles = new Set([
  "apps/api/coverage.json",
  "apps/web/coverage.json",
  "apps/web/tsconfig.app.tsbuildinfo",
  "apps/web/tsconfig.node.tsbuildinfo",
  "scripts/check-terminology.mjs",
  "scripts/test-quality-gates.mjs",
]);
const approvedOrganisationalVocabulary = new Set([
  "analyst",
  "disseminate",
  "dissemination",
  "crioc",
]);
const approvedTechnicalUses = [
  /\bdefence(?:-|_|\s)+in(?:-|_|\s)+depth\b/giu,
  /\bfrom_collection\b/gu,
];
const forbiddenTokens = new Set([
  "chatbot",
  "cm",
  "collection",
  "defence",
  "defense",
  "intelligence",
  "military",
  "rfa",
  "rfi",
]);
const forbiddenPhrases = [
  ["agent", "routing"],
  ["chat", "bot"],
];
const failures = [];

for (const approvedTerm of approvedOrganisationalVocabulary) {
  if (forbiddenTokens.has(approvedTerm)) {
    throw new Error(`Approved organisational term is also forbidden: ${approvedTerm}`);
  }
}

function displayPath(path) {
  return relative(repositoryRoot, path).split(sep).join("/");
}

function tokensFrom(value) {
  const domainVocabulary = approvedTechnicalUses.reduce(
    (remaining, pattern) => remaining.replace(pattern, " "),
    value,
  );
  return domainVocabulary
    .replace(/([a-z0-9])([A-Z])/gu, "$1 $2")
    .replace(/([A-Z]+)([A-Z][a-z])/gu, "$1 $2")
    .toLocaleLowerCase("en-GB")
    .split(/[^a-z0-9]+/u)
    .filter(Boolean);
}

function forbiddenTermsIn(value) {
  const tokens = tokensFrom(value);
  const found = new Set(tokens.filter((token) => forbiddenTokens.has(token)));
  for (const phrase of forbiddenPhrases) {
    for (let index = 0; index <= tokens.length - phrase.length; index += 1) {
      if (phrase.every((token, offset) => tokens[index + offset] === token)) {
        found.add(phrase.join(" "));
      }
    }
  }
  return found;
}

async function requireDirectory(path) {
  let details;
  try {
    details = await stat(path);
  } catch (error) {
    const label = displayPath(path);
    const detail =
      error?.code === "ENOENT"
        ? `Required root is missing: ${label}`
        : `Cannot inspect required root: ${label} (${error.message})`;
    throw new Error(detail, { cause: error });
  }
  if (!details.isDirectory()) {
    throw new Error(`Required root is not a directory: ${displayPath(path)}`);
  }
}

async function inspect(path) {
  let value;
  try {
    value = await readFile(path, "utf8");
  } catch (error) {
    throw new Error(`Cannot read checked file: ${displayPath(path)} (${error.message})`, {
      cause: error,
    });
  }
  for (const term of forbiddenTermsIn(value)) {
    failures.push(`${displayPath(path)}: ${term}`);
  }
}

async function walk(path) {
  let entries;
  try {
    entries = await readdir(path, { withFileTypes: true });
  } catch (error) {
    throw new Error(
      `Cannot read required root tree at ${displayPath(path)} (${error.message})`,
      { cause: error },
    );
  }
  for (const entry of entries) {
    const next = join(path, entry.name);
    const relativePath = displayPath(next);
    if (entry.isDirectory() && !ignoredDirectories.has(entry.name)) await walk(next);
    else if (
      !entry.isDirectory() &&
      !ignoredFiles.has(relativePath) &&
      checked.has(extname(entry.name))
    ) {
      await inspect(next);
    }
  }
}

try {
  for (const root of roots) {
    const path = resolve(repositoryRoot, root);
    await requireDirectory(path);
    await walk(path);
  }
} catch (error) {
  console.error(`Terminology gate could not run: ${error.message}`);
  process.exit(1);
}

if (failures.length) {
  console.error(`Legacy terminology found:\n${failures.join("\n")}`);
  process.exit(1);
}
console.log("Terminology gate passed.");
