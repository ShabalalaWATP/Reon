import { access, readdir, readFile } from "node:fs/promises";
import { dirname, extname, join, resolve } from "node:path";

import {
  pngValidationFailures,
  svgSafetyFailures,
} from "./asset-validation-support.mjs";
import { markdownAnchorIds } from "./markdown-anchor-support.mjs";

const root = process.cwd();
const documents = [
  join(root, "README.md"),
  join(root, "SECURITY.md"),
  join(root, "apps", "api", "README.md"),
  join(root, "infra", "README.md"),
  join(root, "workflow", "README.md"),
  ...(await markdownFiles(join(root, "docs"))),
];
const failures = [];
const screenshotEvidence = join(
  root,
  "docs",
  "assurance",
  "BROWSER_AND_WORKFLOW_EVIDENCE.md",
);
const screenshotDirectory = join(root, "docs", "assets", "screenshots");
const requiredScreenshots = [
  "login.png",
  "password-assistance.png",
  "platform-classification-admin.png",
  "new-service-request-form.png",
  "customer-request-dashboard.png",
  "team-workflow-board.png",
  "routing-workspace-overview.png",
  "team-calendar-manager.png",
  "team-people-manager.png",
].map((filename) => join(screenshotDirectory, filename));
const architectureIndex = join(root, "docs", "README.md");
const architectureDirectory = join(root, "docs", "assets", "architecture");
const architectureRenderer = join(
  root,
  "docs",
  "architecture",
  "structurizr",
  "render-svg.ps1",
);
const requiredArchitectureDiagrams = [
  "01-system-context.svg",
  "02-container-view.svg",
  "03-routing-workflow.svg",
  "04-delivery-workflow.svg",
  "05-durable-workflow-command.svg",
  "06-organisation-routing.svg",
  "07-scanner-supply-chain.svg",
].map((filename) => join(architectureDirectory, filename));
const screenshotReferences = new Set();
const architectureReferences = new Set();
const markdownAnchorCache = new Map();

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
  if (/\bnpx\s+--yes\s+--package\b|\bpnpm\s+dlx\b/iu.test(contents)) {
    failures.push(
      `${document}: documentation must use a frozen workspace dependency, not on-demand package execution`,
    );
  }
  for (const match of contents.matchAll(/!?\[[^\]]*\]\(([^)]+)\)/gu)) {
    const isImage = match[0].startsWith("![");
    const rawTarget = match[1].trim().replace(/^<|>$/gu, "");
    if (
      !rawTarget ||
      /^(?:https?:|mailto:)/u.test(rawTarget)
    ) continue;
    const fragmentSeparator = rawTarget.indexOf("#");
    const pathAndQuery =
      fragmentSeparator === -1
        ? rawTarget
        : rawTarget.slice(0, fragmentSeparator);
    const rawFragment =
      fragmentSeparator === -1 ? "" : rawTarget.slice(fragmentSeparator + 1);
    const pathText = pathAndQuery.split("?", 1)[0];
    let target;
    try {
      target = pathText
        ? resolve(dirname(document), decodeURIComponent(pathText))
        : document;
    } catch {
      failures.push(`${document}: invalid encoded link ${rawTarget}`);
      continue;
    }
    if (document === screenshotEvidence && isImage) {
      screenshotReferences.add(target);
    }
    if (document === architectureIndex) {
      architectureReferences.add(target);
    }
    try {
      await access(target);
    } catch {
      failures.push(`${document}: missing link target ${rawTarget}`);
      continue;
    }
    if (rawFragment && extname(target).toLocaleLowerCase("en-GB") === ".md") {
      let fragment;
      try {
        fragment = decodeURIComponent(rawFragment);
      } catch {
        failures.push(`${document}: invalid encoded fragment ${rawTarget}`);
        continue;
      }
      let anchors = markdownAnchorCache.get(target);
      if (!anchors) {
        anchors = markdownAnchorIds(await readFile(target, "utf8"));
        markdownAnchorCache.set(target, anchors);
      }
      if (!anchors.has(fragment)) {
        failures.push(`${document}: missing Markdown fragment ${rawTarget}`);
      }
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
    for (const failure of pngValidationFailures(contents, 1600, 1000)) {
      failures.push(`${screenshot}: invalid application screenshot: ${failure}`);
    }
  } catch (error) {
    failures.push(`${screenshot}: application screenshot could not be validated: ${error}`);
  }
}

for (const diagram of requiredArchitectureDiagrams) {
  if (!architectureReferences.has(diagram)) {
    failures.push(
      `${architectureIndex}: required architecture diagram is not embedded: ${diagram}`,
    );
  }
  try {
    const contents = await readFile(diagram, "utf8");
    for (const failure of svgSafetyFailures(contents)) {
      failures.push(`${diagram}: unsafe architecture diagram: ${failure}`);
    }
  } catch (error) {
    failures.push(`${diagram}: architecture diagram could not be validated: ${error}`);
  }
}

const rendererContents = await readFile(architectureRenderer, "utf8");
for (const requiredControl of [
  "'--network', 'none'",
  "'--read-only'",
  "'--cap-drop', 'ALL'",
  "'--security-opt', 'no-new-privileges'",
  "'--user', $containerUser",
  "'--tmpfs'",
  "source=${workspacePath}",
]) {
  if (!rendererContents.includes(requiredControl)) {
    failures.push(
      `${architectureRenderer}: sandboxed renderer control is missing: ${requiredControl}`,
    );
  }
}
if (rendererContents.includes("workspaceRoot")) {
  failures.push(
    `${architectureRenderer}: renderer must not expose the repository root to diagram containers`,
  );
}

const scannerDiagram = await readFile(
  join(architectureDirectory, "07-scanner-supply-chain.svg"),
  "utf8",
);
if (
  !scannerDiagram.includes("ClamAVsignatureservice") ||
  !scannerDiagram.includes("[HTTPS]")
) {
  failures.push(
    `${architectureDirectory}: scanner trust view must show the signature service and HTTPS boundary`,
  );
}

if (failures.length > 0) {
  console.error(`Documentation link check failed:\n${failures.join("\n")}`);
  process.exit(1);
}

console.log(`Documentation link check passed for ${documents.length} Markdown files.`);
