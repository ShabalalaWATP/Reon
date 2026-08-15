# ADR 0036: Bounded conversations, packages and actor contexts

## Status

Accepted

## Context

Mist Service already has exact-route monitoring, non-blocking coordination, a
workflow-blocking clarification loop, immutable managed packages, independent
QC dissemination and explicit Customer acceptance. The next product increment
needs a coherent request conversation, a richer package envelope, several QC
Managers and support for identities that may legitimately use both Customer and
staff surfaces.

Flattening these capabilities into one activity feed, one broad product record
or one union of account permissions would create disclosure and separation-of-
duty failures. It would also duplicate the established authorities in ADRs 0010,
0016, 0032, 0033 and 0034.

## Decision

1. Present request discussion as a structured chronological conversation while
   preserving typed domain records. Every entry has a server-owned audience, and
   the persisted default is staff-only. Audience policy is applied before
   pagination. Clarification and return records retain their workflow semantics.
2. Extend managed packages through a versioned envelope containing a covering
   note and ordered manifest. Files, safe raster images and approved external
   links retain independent validation and access controls. Any envelope or
   artefact change creates a new immutable version.
3. Keep one combined QC Team with multiple current Managers, but store QC reviewer
   and releaser as distinct actors for each package version. Final release requires
   a different eligible person and never degrades when staffing is insufficient.
4. Model Customer and staff use as explicit session-bound contexts. Effective
   authority is derived for one context at a time, and protected state is
   namespaced accordingly.
5. Apply a stable-identity self-request conflict rule. A requester cannot later
   route, assign, produce, review or release their own request through staff
   context.
6. Pin legacy requests and packages to the product and workflow rules under which
   they were created. New capabilities are additive and independently gated.

## Consequences

- The user receives one understandable conversation without broadening access or
  turning notification text into a content store.
- Package review covers the exact note, order and artefacts the Customer receives.
- QC requires at least two eligible Managers to complete review and release.
  Staffing shortfall becomes visible operational state.
- Dual-eligible users switch context explicitly, and self-request conflicts remove
  actions rather than relying on navigation preference.
- Conversation, package and context records require versioning, audit, retention,
  legal-hold, migration and reconciliation treatment.
- Rollout needs mixed-version compatibility and fail-closed defaults. Historical
  free text is not reclassified as Customer-visible content.

## Alternatives considered

- **One untyped activity feed:** rejected because workflow events, internal notes,
  Customer messages and clarification have different audiences and effects.
- **One artefact per package:** rejected because it cannot deliver a coherent
  reviewed bundle or covering note without parallel release state.
- **Separate reviewer and release teams:** not required for the pilot. Distinct
  people and action checks within the governed QC Team provide the separation
  while retaining one operational workspace.
- **Union Customer and staff permissions:** rejected because ambient authority
  makes cache, deep-link and self-request conflicts difficult to reason about.
- **Convert all legacy products:** rejected because reconstruction could change
  evidential meaning and invalidate prior approvals.

## Implementation clarification

The immutable package envelope stores a numeric policy version. Migration 0046
backfills existing packages to version 1 and changes only the default for newly
created packages to version 2. Every artefact-addition and submission boundary
validates that pinned version. This is deliberately separate from request product
mode and package sequence number.

Pre-release artefact inspection is an authenticated application stream for clean
managed files and a direct browser link for approved external destinations. The
service never fetches or previews an external destination. Inspection authority is
re-evaluated from live membership, assignment and exact claimed task state on each
request, and inspection does not imply approval or release authority.
