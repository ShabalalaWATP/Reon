import { execFileSync } from "node:child_process";
import {
  copyFile,
  lstat,
  mkdir,
  readlink,
  rename,
  writeFile,
} from "node:fs/promises";
import { dirname, isAbsolute, relative, resolve, sep } from "node:path";

const repositoryRoot = process.cwd();
const destinationArgument = process.argv[2];
if (!destinationArgument) {
  console.error("Usage: node scripts/stage-tracked-source.mjs <new-directory>");
  process.exit(2);
}

const destination = resolve(destinationArgument);
const relativeDestination = relative(repositoryRoot, destination);
if (relativeDestination === "" || !relativeDestination.startsWith(`..${sep}`)) {
  console.error("Tracked-source staging must use a new directory outside the repository.");
  process.exit(2);
}

const trackedOutput = execFileSync("git", ["ls-files", "-z"], {
  cwd: repositoryRoot,
  encoding: "utf8",
  maxBuffer: 32 * 1024 * 1024,
});
const trackedPaths = trackedOutput.split("\0").filter(Boolean);
await mkdir(destination);

for (const trackedPath of trackedPaths) {
  const segments = trackedPath.split("/");
  if (isAbsolute(trackedPath) || segments.includes("..")) {
    throw new Error(`Unsafe tracked path: ${trackedPath}`);
  }
  const source = resolve(repositoryRoot, trackedPath);
  const target = resolve(destination, trackedPath);
  if (relative(destination, target).startsWith("..")) {
    throw new Error(`Tracked path escapes staging directory: ${trackedPath}`);
  }
  await mkdir(dirname(target), { recursive: true });
  const details = await lstat(source);
  if (details.isSymbolicLink()) {
    await writeFile(target, await readlink(source));
  } else {
    await copyFile(source, target);
  }
}

const dockerIgnorePaths = [
  ".dockerignore",
  "scripts/secret-scan.Dockerfile.dockerignore",
];
for (const path of dockerIgnorePaths) {
  await rename(
    resolve(destination, path),
    resolve(destination, `${path}.tracked-source`),
  );
}
await writeFile(
  resolve(destination, "tracked-source-inventory.txt"),
  `${trackedPaths.join("\n")}\n`,
);
console.log(`Staged ${trackedPaths.length} tracked files for source scanning.`);
