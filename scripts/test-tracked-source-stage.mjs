import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import {
  access,
  mkdir,
  mkdtemp,
  readFile,
  rm,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const stageScript = join(scriptDirectory, "stage-tracked-source.mjs");
const fixture = await mkdtemp(join(tmpdir(), "mist-tracked-source-"));
const repository = join(fixture, "repository");
const staged = join(fixture, "staged");

try {
  await mkdir(join(repository, "scripts"), { recursive: true });
  await writeFile(join(repository, ".dockerignore"), ".env*\n");
  await writeFile(join(repository, ".env.production"), "SYNTHETIC=value\n");
  await writeFile(
    join(repository, "scripts/secret-scan.Dockerfile.dockerignore"),
    ".env*\n",
  );
  await writeFile(join(repository, "safe.txt"), "safe\n");
  execFileSync("git", ["init", "--quiet"], { cwd: repository });
  execFileSync("git", ["add", "--force", "."], { cwd: repository });

  execFileSync(process.execPath, [stageScript, staged], { cwd: repository });

  assert.equal(
    await readFile(join(staged, ".env.production"), "utf8"),
    "SYNTHETIC=value\n",
    "force-added environment files must remain in the scan context",
  );
  await access(join(staged, ".dockerignore.tracked-source"));
  await access(
    join(staged, "scripts/secret-scan.Dockerfile.dockerignore.tracked-source"),
  );
  const inventory = await readFile(
    join(staged, "tracked-source-inventory.txt"),
    "utf8",
  );
  assert.match(inventory, /^\.env\.production$/mu);
} finally {
  await rm(fixture, { recursive: true, force: true });
}

console.log("Tracked-source staging tests passed.");
