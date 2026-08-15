import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const gate = join(scriptDirectory, "check-trufflehog-findings.mjs");
const dockerfile = join(scriptDirectory, "trufflehog-scan.Dockerfile");
const root = await mkdtemp(join(tmpdir(), "mist-trufflehog-gate-"));
const findingsPath = join(root, "findings.jsonl");
const allowlistPath = join(root, "allowlist.json");
const raw = `https://${["test-user", "test-pass"].join(":")}@example.test/a`;
const finding = {
  SourceMetadata: {
    Data: { Git: { commit: "a".repeat(40), file: "fixture.ts", line: 4 } },
  },
  DetectorName: "URI",
  RawV2: raw,
  Verified: false,
};

function idFor(value) {
  return createHash("sha256")
    .update([value.DetectorName, value.RawV2 || value.Raw].join("|"))
    .digest("hex");
}

function run() {
  return spawnSync(process.execPath, [gate, findingsPath, allowlistPath], {
    encoding: "utf8",
    windowsHide: true,
  });
}

async function write(findingRows, entries) {
  await writeFile(
    findingsPath,
    findingRows.map((item) => JSON.stringify(item)).join("\n"),
  );
  await writeFile(
    allowlistPath,
    JSON.stringify({ version: 1, entries }),
  );
}

const approved = {
  fingerprint: idFor(finding),
  expiresOn: "2099-01-01",
  reason: "Synthetic exact test fixture with no external value.",
};
try {
  const dockerfileSource = await readFile(dockerfile, "utf8");
  assert.match(
    dockerfileSource,
    /FROM scratch AS evidence\s+COPY --from=gate /u,
    "the evidence target must depend on the policy gate",
  );

  await write([finding], [approved]);
  assert.equal(run().status, 0);

  await write([{ ...finding, Verified: true }], [approved]);
  assert.notEqual(run().status, 0);

  await write(
    [{ ...finding, Verified: true, Raw: raw, RawV2: "" }],
    [{ ...approved, allowVerifiedFalsePositive: true }],
  );
  assert.equal(run().status, 0);

  await write(
    [{ ...finding, SourceMetadata: { Data: { Filesystem: { file: "fixture.ts", line: 4 } } } }],
    [approved],
  );
  assert.notEqual(run().status, 0);

  // A commit-message match has no file path: it must still fail closed and
  // pass only with an exact exception for its detector and matched value.
  const messageRaw = `${raw}-in-a-commit-message`;
  const messageFinding = {
    ...finding,
    Verified: true,
    RawV2: messageRaw,
    SourceMetadata: { Data: { Git: { commit: "b".repeat(40) } } },
  };
  const messageId = createHash("sha256")
    .update([finding.DetectorName, messageRaw].join("|"))
    .digest("hex");
  await write([messageFinding], []);
  assert.notEqual(run().status, 0);
  await write(
    [messageFinding],
    [
      {
        fingerprint: messageId,
        expiresOn: "2099-01-01",
        reason: "Synthetic commit-message fixture with no external value.",
        allowVerifiedFalsePositive: true,
      },
    ],
  );
  assert.equal(run().status, 0);

  await write(
    [
      {
        ...finding,
        RawV2: `${raw}-changed`,
      },
    ],
    [approved],
  );
  assert.notEqual(run().status, 0);

  await write([finding], [{ ...approved, expiresOn: "2020-01-01" }]);
  assert.notEqual(run().status, 0);

  await write([], []);
  assert.equal(run().status, 0);
} finally {
  await rm(root, { recursive: true, force: true });
}

console.log("TruffleHog gate tests passed.");
