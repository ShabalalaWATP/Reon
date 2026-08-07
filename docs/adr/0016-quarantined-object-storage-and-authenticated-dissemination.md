# ADR 0016: Quarantined Object Storage and Authenticated Dissemination

## Status

Accepted for implementation on 7 August 2026. File-size, retention, production
storage and scanner-owner decisions remain release gates.

## Context

The current authorised plain-text download cannot safely carry managed PDF,
DOCX or PPTX products. Binary products create malware, active-content, object
access and lifecycle boundaries. Approved external product links create a
separate redirect and recipient-authorisation boundary.

## Decision

- Keep package, artefact, checksum, scan, lifecycle, recipient and access metadata
  in PostgreSQL. Keep bytes in private S3-compatible quarantine and released
  storage; never store file bytes in PostgreSQL or expose public object URLs.
- Issue short-lived, single-purpose upload intents with a server-chosen key,
  expected media type and size bound. An intent cannot address another object or
  released storage.
- Before promotion, validate extension, declared and detected media type, magic
  bytes, Office package structure, encryption, archive expansion and active
  content, then require a current clean malware result. Failed, unknown, stale or
  timed-out results cannot enter review or dissemination.
- Make release-package versions immutable. Team Manager review and independent QC
  dissemination bind to the exact package version and checksum. Any artefact
  change creates a new version and invalidates earlier approval.
- Authorise every download against the active Customer, dissemination and
  artefact lifecycle. Use short-lived object grants or application streaming with
  `no-store`, `nosniff`, safe attachment filenames and explicit disposition.
- Accept only absolute HTTPS external links matching a versioned administrator
  allow-list. Reject credentials, fragments, non-standard schemes, loopback and
  literal private-network hosts. The backend does not fetch or preview the
  destination.
- Open an external product only through an authenticated application redirect
  that rechecks the release and recipient, records a content-free access event
  and applies safe browser isolation. QC explicitly attests recipient access and
  handling suitability before dissemination.

## Consequences

- Storage, scanner and database changes need idempotent promotion, reconciliation,
  orphan cleanup and joined recovery evidence.
- Replaced, withdrawn, expired or unavailable artefacts remain attributable in
  history but cannot be opened.
- Local development may use compatible local services. Production region,
  encryption-key ownership, scanner operation and retention must be approved
  separately.
- Email, Teams, public shares and other connectors remain out of scope.

## Rejected alternatives

- Store binaries in PostgreSQL: this couples database recovery and product-byte
  retention unnecessarily.
- Scan after release: an unsafe or unknown object could reach a Customer.
- Backend link preview: this introduces SSRF and content-ingestion boundaries.
- Trust a bucket URL: possession would bypass current object and recipient policy.
