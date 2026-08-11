import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, join, posix } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const root = join(scriptDirectory, "..");
const [config, compose] = await Promise.all([
  readFile(join(root, ".github", "dependabot.yml"), "utf8"),
  readFile(join(root, "docker-compose.yml"), "utf8"),
]);

function repositoryName(image) {
  const withoutDigest = image.trim().replace(/^['"]|['"]$/gu, "").split("@")[0];
  const lastSlash = withoutDigest.lastIndexOf("/");
  const lastColon = withoutDigest.lastIndexOf(":");
  return lastColon > lastSlash ? withoutDigest.slice(0, lastColon) : withoutDigest;
}

function indentation(line) {
  return line.match(/^ */u)[0].length;
}

function collectBlocks(lines, start, end, indent, keyPattern) {
  const blocks = [];
  for (let index = start; index < end; index += 1) {
    if (!keyPattern.test(lines[index])) continue;
    let next = index + 1;
    while (next < end) {
      const candidate = lines[next];
      if (
        candidate.trim() &&
        !candidate.trimStart().startsWith("#") &&
        indentation(candidate) <= indent
      ) {
        break;
      }
      next += 1;
    }
    blocks.push(lines.slice(index, next).join("\n"));
    index = next - 1;
  }
  return blocks;
}

const composeLines = compose.split(/\r?\n/u);
const servicesStart = composeLines.findIndex((line) => line === "services:");
assert.ok(servicesStart >= 0, "Compose services section is missing");
const servicesEndCandidate = composeLines.findIndex(
  (line, index) =>
    index > servicesStart &&
    line.trim() &&
    !line.startsWith("#") &&
    indentation(line) === 0,
);
const servicesEnd = servicesEndCandidate < 0 ? composeLines.length : servicesEndCandidate;
const extensionBlocks = collectBlocks(
  composeLines,
  0,
  servicesStart,
  0,
  /^x-[\w-]+:/u,
);
const serviceBlocks = collectBlocks(
  composeLines,
  servicesStart + 1,
  servicesEnd,
  2,
  /^  [\w-]+:/u,
);

const localImages = new Map();
for (const block of [...extensionBlocks, ...serviceBlocks]) {
  const image = block.match(/^\s+image:\s*([^\r\n]+)/mu)?.[1];
  const dockerfile = block.match(/\bdockerfile:\s*([^,}\s]+)/u)?.[1];
  if (image && dockerfile && /^\s+build:/mu.test(block)) {
    localImages.set(repositoryName(image), dockerfile);
  }
}
assert.equal(localImages.size, 5, "expected five locally built Compose images");

const allImages = new Set(
  [...compose.matchAll(/^\s+image:\s*([^\r\n]+)/gmu)].map((match) =>
    repositoryName(match[1]),
  ),
);
const externalImages = new Set(
  [...allImages].filter((image) => !localImages.has(image)),
);
assert.ok(externalImages.size > 0, "expected at least one external Compose image");

const updaterBlocks = config
  .split(/^  - package-ecosystem:\s*/mu)
  .slice(1)
  .map((block) => {
    const [ecosystem, ...lines] = block.split(/\r?\n/u);
    const body = lines.join("\n");
    const directory = body.match(/^\s{4}directory:\s*(\S+)/mu)?.[1];
    assert.ok(directory, `missing directory for ${ecosystem}`);
    return { body, directory, ecosystem };
  });
const updaterScopes = new Set(
  updaterBlocks.map(({ directory, ecosystem }) => `${ecosystem}:${directory}`),
);
for (const requiredScope of ["uv:/apps/api", "docker:/scripts"]) {
  assert.ok(updaterScopes.has(requiredScope), `missing updater scope: ${requiredScope}`);
}

const composeUpdater = updaterBlocks.find(
  ({ directory, ecosystem }) => ecosystem === "docker-compose" && directory === "/",
);
assert.ok(composeUpdater, "root Compose updater is missing");
const ignoredImages = new Set(
  [...composeUpdater.body.matchAll(/^\s+- dependency-name:\s*(\S+)/gmu)].map(
    (match) => match[1],
  ),
);
assert.deepEqual(
  [...ignoredImages].sort(),
  [...localImages.keys()].sort(),
  "Compose ignores must exactly equal the locally built image repositories",
);

for (const [image, dockerfile] of localImages) {
  const dockerDirectory = `/${posix.dirname(dockerfile)}`;
  assert.ok(
    updaterScopes.has(`docker:${dockerDirectory}`),
    `${image} must map to a Dependabot-managed Dockerfile directory`,
  );
}
for (const externalImage of externalImages) {
  assert.ok(
    !ignoredImages.has(externalImage),
    `external Compose image must remain updateable: ${externalImage}`,
  );
}

console.log("Dependabot configuration contract passed.");
