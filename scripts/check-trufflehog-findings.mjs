import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import process from "node:process";

const findingsPath = process.argv[2];
const allowlistPath = process.argv[3];
if (!findingsPath || !allowlistPath) {
  console.error("Usage: node check-trufflehog-findings.mjs FINDINGS ALLOWLIST");
  process.exit(2);
}

function fingerprint(finding) {
  const git = finding?.SourceMetadata?.Data?.Git;
  const fields = [
    git?.commit,
    git?.file,
    finding?.DetectorName,
  ];
  if (fields.some((value) => !value)) {
    throw new Error("A TruffleHog finding lacks stable Git fingerprint fields.");
  }
  return createHash("sha256").update(fields.join("|"), "utf8").digest("hex");
}

function parseFindings(content) {
  return content
    .split(/\r?\n/u)
    .filter((line) => line.trim())
    .map((line, index) => {
      try {
        return JSON.parse(line);
      } catch (error) {
        throw new Error(`Invalid TruffleHog JSON on line ${index + 1}.`, {
          cause: error,
        });
      }
    });
}

function activeAllowlist(document) {
  if (document?.version !== 1 || !Array.isArray(document.entries)) {
    throw new Error("The TruffleHog allow-list schema is invalid.");
  }
  const today = new Date().toISOString().slice(0, 10);
  const entries = new Map();
  for (const entry of document.entries) {
    if (
      !/^[a-f0-9]{64}$/u.test(entry?.fingerprint ?? "") ||
      !/^\d{4}-\d{2}-\d{2}$/u.test(entry?.expiresOn ?? "") ||
      typeof entry?.reason !== "string" ||
      entry.reason.trim().length < 20 ||
      (entry.allowVerifiedFalsePositive !== undefined &&
        typeof entry.allowVerifiedFalsePositive !== "boolean")
    ) {
      throw new Error("A TruffleHog allow-list entry is incomplete.");
    }
    if (entry.expiresOn < today) {
      throw new Error(`TruffleHog exception ${entry.fingerprint} has expired.`);
    }
    if (entries.has(entry.fingerprint)) {
      throw new Error(`Duplicate TruffleHog exception ${entry.fingerprint}.`);
    }
    entries.set(entry.fingerprint, entry);
  }
  return entries;
}

try {
  const [findingText, allowlistText] = await Promise.all([
    readFile(findingsPath, "utf8"),
    readFile(allowlistPath, "utf8"),
  ]);
  const findings = parseFindings(findingText);
  const approved = activeAllowlist(JSON.parse(allowlistText));
  const observed = new Set();
  const failures = [];
  for (const finding of findings) {
    const id = fingerprint(finding);
    const exception = approved.get(id);
    if (finding.Verified === true && !exception?.allowVerifiedFalsePositive) {
      failures.push(`verified secret ${id}`);
      continue;
    }
    if (!exception) {
      failures.push(`unapproved unknown finding ${id}`);
      continue;
    }
    observed.add(id);
  }
  for (const id of approved.keys()) {
    if (!observed.has(id)) {
      failures.push(`stale exception ${id}`);
    }
  }
  if (failures.length) {
    throw new Error(`TruffleHog gate failed: ${failures.join(", ")}`);
  }
  console.log(
    `TruffleHog gate passed: ${findings.length} finding(s), ${observed.size} exact exception(s).`,
  );
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
}
