import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const read = (path) => readFile(join(root, path), "utf8");
const [workflow, compose, config, journey, webPackage] = await Promise.all([
  read(".github/workflows/browser.yml"),
  read(".github/compose.browser.yml"),
  read("apps/web/playwright.config.ts"),
  read("apps/web/e2e/primary-workflow.spec.ts"),
  read("apps/web/package.json"),
]);
const compactWorkflow = workflow.replace(/\s+/gu, " ");

for (const required of [
  "pull_request:",
  "branches: [main]",
  "permissions:",
  "contents: read",
  "timeout-minutes: 35",
  "playwright install --with-deps chromium",
  "docker-compose.yml -f .github/compose.browser.yml up --build --detach --wait",
  "pnpm --filter @istari-service/web test:e2e",
  "if: failure()",
  "if: always()",
  "down --volumes --remove-orphans",
]) {
  assert.ok(compactWorkflow.includes(required), `browser workflow is missing: ${required}`);
}
assert.doesNotMatch(workflow, /DEMO_USER_PASSWORD:\s*[^$\s]/u);
assert.match(workflow, /openssl rand -hex 24/u);
assert.match(workflow, /actions\/checkout@[a-f0-9]{40}/u);
assert.match(workflow, /actions\/upload-artifact@[a-f0-9]{40}/u);

for (const required of [
  'MANAGED_PRODUCTS_ENABLED: "true"',
  'MANAGED_FILE_UPLOADS_ENABLED: "false"',
  "PRODUCT_ALLOWED_EXTERNAL_DOMAINS: products.example.test",
]) {
  assert.ok(compose.includes(required), `browser Compose override is missing: ${required}`);
}

for (const required of [
  'name: "chromium"',
  'screenshot: "only-on-failure"',
  'trace: "retain-on-failure"',
  'video: "off"',
  "workers: 1",
  "fullyParallel: false",
]) {
  assert.ok(config.includes(required), `Playwright config is missing: ${required}`);
}
assert.ok(!config.includes("webServer"), "CI must exercise the retained Compose topology");

for (const required of [
  'signIn(page, "admin2"',
  'switchIdentity(page, "admin4"',
  'switchIdentity(page, "admin5"',
  'switchIdentity(page, "admin6"',
  'switchIdentity(page, "admin8"',
  'switchIdentity(page, "admin13"',
  'switchIdentity(page, "admin15"',
  'switchIdentity(page, "admin100"',
  'switchContext(page, "Customer")',
  'switchContext(page, "Staff")',
  '"Accept product"',
  "monitor.assertClean()",
]) {
  assert.ok(journey.includes(required), `browser journey is missing: ${required}`);
}

const packageDocument = JSON.parse(webPackage);
assert.equal(packageDocument.scripts["test:e2e"], "playwright test");
assert.equal(packageDocument.devDependencies["@playwright/test"], "1.62.1");

console.log("Real-browser workflow contract passed.");
