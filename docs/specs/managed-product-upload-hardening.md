# Managed product upload hardening

## Purpose

Managed product files must not exhaust metadata, storage, scanner or local
filesystem resources before the existing review lifecycle can reject them.

## Requirements

- Reserve declared bytes before issuing an upload grant. Enforce the 100 MiB
  package aggregate plus bounded request, author and service totals.
- Permit one active draft per request and at most 100 immutable package versions.
- Treat pending and quarantined artefact sizes as reserved storage. Failed and
  expired artefacts release their reservation.
- Keep grants opaque, short-lived and bounded in memory. Purge expired grants and
  evict the earliest expiry when the configured cache bound is reached.
- Compensate object writes and promotions when database finalisation fails.
- Run a fenced, bounded maintenance reconciliation that expires abandoned intents
  and deletes unreferenced quarantine objects idempotently.
- Reject multi-disk, Zip64 and excessive Office central directories before Python's
  ZIP parser materialises entry metadata. Reject ambiguous archive paths before
  extraction and parse XML with DTD, entity, depth, node and attribute limits.
- Decode OOXML relationship and field-instruction semantics before deciding that
  active content is absent. Inspect PDF name objects outside inert strings,
  comments and stream bodies, and fail closed on unsupported active capabilities.
- Acquire the composite scan semaphore before advancing the upload stream or
  creating its first spool. Hold the slot through structure inspection and
  malware scanning, and bound the API container's `/tmp` filesystem to 256 MiB.
- Cancellation before promotion releases the scan lease for retry. Cancellation
  after promotion begins performs no destructive compensation because the
  object/database outcome is then ambiguous.
- The local filesystem adapter must contain object keys, reject symbolic links,
  use no-follow reads where the operating system supports them and preserve atomic
  writes. Windows environments without symbolic-link privilege may skip only the
  malicious-link fixture, not the containment checks.

## Acceptance evidence

- A second artefact that exceeds aggregate capacity is rejected before a grant.
- Storage scope checks are serialised by the singleton quota row and locked owner,
  request and package rows.
- Post-write and post-promotion database failures remove their orphan objects.
- Expired intent and orphan cleanup is retry-safe and batch bounded.
- Zip64 sentinel metadata is rejected before `ZipFile` construction and concurrent
  inspection never exceeds its semaphore capacity, including source iteration
  and the first spool.
- Encoded OOXML relationships and field instructions, canonical PDF actions and
  inert PDF lexical controls have adversarial regression coverage.
