import { access, readdir, readFile } from "node:fs/promises";
import { dirname, extname, join, resolve } from "node:path";

const root = process.cwd();
const documents = [join(root, "README.md"), ...(await markdownFiles(join(root, "docs")))];
const failures = [];
const screenshotEvidence = join(
  root,
  "docs",
  "assurance",
  "BROWSER_AND_WORKFLOW_EVIDENCE.md",
);
const requiredScreenshots = [
  join(root, "docs", "assets", "screenshots", "login.png"),
  join(root, "docs", "assets", "screenshots", "new-service-request-form.png"),
  join(root, "docs", "assets", "screenshots", "customer-request-dashboard.png"),
  join(root, "docs", "assets", "screenshots", "team-workflow-board.png"),
];
const screenshotReferences = new Set();

async function markdownFiles(path) {
  const files = [];
  for (const entry of await readdir(path, { withFileTypes: true })) {
    const next = join(path, entry.name);
    if (entry.isDirectory()) files.push(...(await markdownFiles(next)));
    else if (extname(entry.name) === ".md") files.push(next);
  }
  return files;
}

for (const document of documents) {
  const contents = await readFile(document, "utf8");
  for (const match of contents.matchAll(/!?\[[^\]]*\]\(([^)]+)\)/gu)) {
    const isImage = match[0].startsWith("![");
    const rawTarget = match[1].trim().replace(/^<|>$/gu, "");
    if (
      !rawTarget ||
      rawTarget.startsWith("#") ||
      /^(?:https?:|mailto:)/u.test(rawTarget)
    ) continue;
    const pathText = rawTarget.split("#", 1)[0].split("?", 1)[0];
    if (!pathText) continue;
    let target;
    try {
      target = resolve(dirname(document), decodeURIComponent(pathText));
    } catch {
      failures.push(`${document}: invalid encoded link ${rawTarget}`);
      continue;
    }
    if (document === screenshotEvidence && isImage) {
      screenshotReferences.add(target);
    }
    try {
      await access(target);
    } catch {
      failures.push(`${document}: missing link target ${rawTarget}`);
    }
  }
}

for (const screenshot of requiredScreenshots) {
  if (!screenshotReferences.has(screenshot)) {
    failures.push(
      `${screenshotEvidence}: required application screenshot is not embedded: ${screenshot}`,
    );
  }
  try {
    const contents = await readFile(screenshot);
    const pngSignature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
    const hasPngSignature =
      contents.length >= pngSignature.length &&
      contents.subarray(0, pngSignature.length).equals(pngSignature);
    if (!hasPngSignature) {
      failures.push(`${screenshot}: required application screenshot is not a valid PNG file`);
    }
  } catch {
    // The link check above already reports a missing target with document context.
  }
}

if (failures.length > 0) {
  console.error(`Documentation link check failed:\n${failures.join("\n")}`);
  process.exit(1);
}

console.log(`Documentation link check passed for ${documents.length} Markdown files.`);
