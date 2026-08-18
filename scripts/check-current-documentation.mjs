import { access, readFile } from "node:fs/promises";
import { join, resolve } from "node:path";

const root = process.cwd();
const currentGuides = [
  "README.md",
  "SECURITY.md",
  "apps/api/README.md",
  "infra/README.md",
  "workflow/README.md",
  "docs/README.md",
  "docs/ENTERPRISE_READINESS_GAP_REGISTER.md",
  "docs/USER_STORIES.md",
  "docs/adr/README.md",
  "docs/architecture/README.md",
  "docs/architecture/SYSTEM_ARCHITECTURE.md",
  "docs/architecture/WORKFLOW_AND_BPMN.md",
  "docs/architecture/ORGANISATION_AND_ROUTING.md",
  "docs/architecture/structurizr/README.md",
  "docs/assurance/README.md",
  "docs/reference/ROLE_PERMISSION_MATRIX.md",
  "docs/deployment/README.md",
  "docs/deployment/HOST_SETUP.md",
  "docs/deployment/LOCAL_DOCKER.md",
  "docs/deployment/LOCAL_SOURCE_DEVELOPMENT.md",
  "docs/deployment/AWS_SANDBOX.md",
  "docs/deployment/GCP_SANDBOX.md",
  "docs/deployment/AZURE_SANDBOX.md",
  "docs/deployment/KUBERNETES_TARGET.md",
  "docs/deployment/CONFIGURATION_REFERENCE.md",
  "docs/deployment/PRODUCTION_GATES.md",
  "docs/deployment/RELEASE_RUNBOOK.md",
  "docs/operations/README.md",
  "docs/operations/BACKUP_RESTORE_AND_MAINTENANCE.md",
  "docs/operations/BUSINESS_CONTINUITY_AND_DISASTER_RECOVERY.md",
  "docs/operations/CONFIGURATION_AND_ROUTING_RUNBOOK.md",
  "docs/operations/SUPPORT_AND_INCIDENT_RUNBOOK.md",
  "docs/security/README.md",
  "docs/security/AUDIT_EVENT_CATALOGUE.md",
  "docs/security/LICENCE_POLICY.md",
  "docs/specs/README.md",
  "docs/threat-model/README.md",
  "docs/threat-model/management-and-analytics.md",
  "docs/threat-model/operations-and-recovery.md",
  "docs/threat-model/platform-administration.md",
  "docs/threat-model/service-request-workflow.md",
  "docs/threat-model/team-workspaces-and-calendars.md",
];
const staleCurrentStateTerms = [
  "RequestMessageForm",
  "planning-cockpit projection",
  "Advanced Planning and Handover",
  "product repository god interface",
  "ADRs 0001 to 0030",
];
const requiredCoverage = new Map([
  ["README.md", ["Customer and Staff contexts", "Structured request conversations"]],
  [
    "docs/architecture/SYSTEM_ARCHITECTURE.md",
    ["Current technology baseline", "SQLite quarantine index", "Structurizr workspace"],
  ],
  [
    "docs/deployment/HOST_SETUP.md",
    ["Windows 11", "MacBook", "Linux workstation or private VM", "AWS", "Google Cloud"],
  ],
]);
const sourcePrefixes = ["apps/", "docs/", "infra/", "scripts/", "workflow/", ".github/"];
const sourceNames = new Set([
  ".env.example",
  "README.md",
  "SECURITY.md",
  "docker-compose.yml",
  "package.json",
  "pnpm-lock.yaml",
  "uv.lock",
]);
const failures = [];

function inlineCode(contents) {
  return [...contents.matchAll(/`([^`\r\n]+)`/gu)].map((match) => match[1]);
}

function sourceReference(token) {
  const normalised = token.replaceAll("\\", "/").replace(/^\.\//u, "");
  if (sourceNames.has(normalised)) return normalised;
  if (!sourcePrefixes.some((prefix) => normalised.startsWith(prefix))) return null;
  if (/\s|[<>*{}|]/u.test(normalised)) return null;
  return normalised.replace(/[.,:;]+$/u, "");
}

for (const guide of currentGuides) {
  const absolute = join(root, guide);
  let contents;
  try {
    contents = await readFile(absolute, "utf8");
  } catch {
    failures.push(`${guide}: current-state guide is missing`);
    continue;
  }
  for (const term of staleCurrentStateTerms) {
    if (contents.includes(term)) failures.push(`${guide}: stale current-state term: ${term}`);
  }
  for (const phrase of requiredCoverage.get(guide) ?? []) {
    if (!contents.includes(phrase)) failures.push(`${guide}: required current coverage missing: ${phrase}`);
  }
  for (const token of inlineCode(contents)) {
    const reference = sourceReference(token);
    if (!reference) continue;
    try {
      await access(resolve(root, reference));
    } catch {
      failures.push(`${guide}: source reference does not exist: ${reference}`);
    }
  }
}

if (failures.length > 0) {
  console.error(`Current documentation check failed:\n${failures.join("\n")}`);
  process.exit(1);
}

console.log(
  `Current documentation check passed for ${currentGuides.length} guides and their source references.`,
);
