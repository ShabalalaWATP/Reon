import { readdir, readFile, stat } from "node:fs/promises";
import { extname, join, relative, resolve, sep } from "node:path";

const repositoryRoot = process.cwd();
const roots = [
  ".github",
  "apps/api/src",
  "apps/api/tests",
  "apps/web/src",
  "apps/web/scripts",
  "infra",
  "scripts",
  "workflow",
];
const targets = [
  "package.json",
  "pnpm-workspace.yaml",
  "docker-compose.yml",
  "apps/api/Dockerfile",
  "apps/api/alembic.ini",
  "apps/api/alembic/env.py",
  "apps/api/alembic/script.py.mako",
  "apps/api/pyproject.toml",
  "apps/web/Dockerfile",
  "apps/web/eslint.config.js",
  "apps/web/index.html",
  "apps/web/nginx.conf",
  "apps/web/package.json",
  "apps/web/vite.config.ts",
];
const checked = new Set([
  ".bpmn",
  ".css",
  ".Dockerfile",
  ".js",
  ".mjs",
  ".ps1",
  ".py",
  ".sh",
  ".ts",
  ".tsx",
  ".yaml",
  ".yml",
]);
const checkedNames = new Set(["Dockerfile"]);
const failures = [];

function displayPath(path) {
  return relative(repositoryRoot, path).split(sep).join("/");
}

function inspectionError(kind, path, error) {
  const label = displayPath(path);
  if (error?.code === "ENOENT") return `Required ${kind} is missing: ${label}`;
  return `Cannot inspect required ${kind}: ${label} (${error.message})`;
}

async function requireDirectory(path) {
  let details;
  try {
    details = await stat(path);
  } catch (error) {
    throw new Error(inspectionError("root", path, error), { cause: error });
  }
  if (!details.isDirectory()) {
    throw new Error(`Required root is not a directory: ${displayPath(path)}`);
  }
}

async function check(path, requiredTarget = false) {
  let value;
  try {
    value = await readFile(path, "utf8");
  } catch (error) {
    const kind = requiredTarget ? "required target" : "checked file";
    throw new Error(`Cannot read ${kind}: ${displayPath(path)} (${error.message})`, {
      cause: error,
    });
  }
  const lines = value.length === 0 ? [] : value.split(/\r\n|\n|\r/u);
  if (lines.at(-1) === "") lines.pop();
  const count = lines.length;
  if (count > 350) failures.push(`${displayPath(path)}: ${count} lines`);
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
    if (entry.isDirectory()) await walk(next);
    else if (checked.has(extname(entry.name)) || checkedNames.has(entry.name)) {
      await check(next);
    }
  }
}

async function checkTarget(target) {
  const path = resolve(repositoryRoot, target);
  let details;
  try {
    details = await stat(path);
  } catch (error) {
    throw new Error(inspectionError("target", path, error), { cause: error });
  }
  if (!details.isFile()) {
    throw new Error(`Required target is not a file: ${displayPath(path)}`);
  }
  await check(path, true);
}

try {
  for (const root of roots) {
    const path = resolve(repositoryRoot, root);
    await requireDirectory(path);
    await walk(path);
  }
  for (const target of targets) await checkTarget(target);
} catch (error) {
  console.error(`Line-limit gate could not run: ${error.message}`);
  process.exit(1);
}

if (failures.length) {
  console.error(`Hand-written files exceed 350 lines:\n${failures.join("\n")}`);
  process.exit(1);
}
console.log("Line limit passed.");
