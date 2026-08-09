# ADR 0021: Shared login throttling and hardened runtime images

Status: accepted
Date: 9 August 2026

## Context

The local account lock was stored against one known account and did not bound
unknown-account Argon2 work across API replicas. Proxy-derived client addresses
also need an explicit trust boundary. Separately, the release topology inherited
unused packages and privileges from upstream database, workflow, scanner and web
images. Container scans covered only the API and web images, and scanner health
did not prove that the running daemon had loaded current signatures.

The synthetic MVP authentication contract remains unchanged by product-owner
decision. This ADR protects its resources and deployment boundary without
presenting that account model as production identity.

## Decision

1. Durably consume global and source-specific login capacity in a separate,
   cancellation-shielded PostgreSQL transaction before any account lookup or
   Argon2 verification. Enforce an end-to-end acquisition/transaction deadline
   plus shorter transaction-local statement and lock deadlines. Release the
   shared row lock before hashing begins and fail unavailable before hashing if
   the budget cannot be committed in time.
2. Store a one-way digest of the canonical source address, never a raw address
   or username, and use an atomic fixed-window upsert shared by all replicas.
3. Trust one forwarded address only when the direct peer belongs to an
   explicitly configured proxy CIDR. Otherwise use the direct peer.
4. Bound concurrent Argon2 work independently in every API process.
5. Return one account-neutral `429` response with a bounded `Retry-After` value.
6. Build minimal, digest-pinned runtime images. Run PostgreSQL, Camunda, API,
   worker and web processes without root privileges or Linux capabilities after
   any narrowly scoped initialisation step.
7. Split ClamAV into an internal-only, read-only clamd process and a separate
   signature updater with outbound mirror access. Both run non-root without
   capabilities. Health uses the signed database build timestamp and requires
   the same definition version on disk and loaded by clamd.
8. Build and scan every deployed image in CI, fail on high or critical findings,
   and retain one CycloneDX SBOM per image.
9. Permit a secret-scan exception only for an exact stable fingerprint with a
   reason and expiry. Verified secrets can never be excepted.
10. Delay ordinary package resolutions and Dependabot version updates by seven
    days. Keep any bootstrap exception exact to a previously locked and scanned
    version so it cannot authorise a later release.

## Consequences

- Login attempts add a small database write before credential verification.
- A database outage fails authentication closed instead of falling back to an
  in-memory budget.
- Database and row-lock contention returns an account-neutral temporary
  unavailable response within the configured deadline; it cannot leave an
  unbounded cancellation-shielded task.
- Deployment owners must configure trusted proxy CIDRs from the actual ingress
  topology and monitor global throttle saturation.
- ClamAV startup can take longer while signatures update and the daemon reloads.
- Only the updater receives outbound update access in local Compose. The clamd
  process that parses untrusted content and the API remain internal-only.
- Upstream image updates require rebuild, smoke and vulnerability evidence for
  all five deployed images.
- Existing Node lock entries newer than the policy require exact-version
  bootstrap exceptions. Those entries remain subject to audit and image scans;
  any later version must satisfy the normal age and trust policy.
- Edge WAF controls remain required for defence in depth and broad volumetric
  attacks. Application throttling is not a substitute for an approved ingress.

## Alternatives rejected

- Per-process counters allow limits to multiply with replicas and reset on
  restart.
- Account-only counters expose unknown-account hash work and create different
  observable behaviour for known and unknown usernames.
- Trusting arbitrary `X-Forwarded-For` values lets clients choose their own rate
  buckets.
- Running an extra Redis dependency solely for the MVP throttle adds an
  operational boundary when PostgreSQL already provides atomic shared state.
- Treating file modification time as sufficient scanner health can report ready
  while clamd still uses older loaded definitions.

## Out of scope

- Replacement of synthetic local accounts with OIDC, MFA or enterprise identity.
- GitHub branch-protection policy.
- Production WAF, certificate, ingress and network-policy implementation.
