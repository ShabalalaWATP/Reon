# ADR 0018: Guided configuration change workspace

## Status

Accepted for implementation on 7 August 2026. It supersedes only the user-facing
terminology of ADR 0017, not its immutable revision, approval or pinning model.

## Context

Platform Administrators need to change an organisation that may grow from tens
to thousands of units. Exposing database concepts such as draft versions and
record counters caused confusion between the current configuration and work in
progress. An unrestricted hierarchy selector also made invalid parents easy to
choose, while a flat tree made large structures expensive to scan.

Removing immutable revisions would create a larger problem: silent concurrent
overwrites, ambiguous approval, destructive rollback and changed in-flight
routing. The user experience therefore needs simplification without weakening
the governance boundary.

## Decision

- Present `Current configuration`, `Proposed changes`, `Ready for review`,
  `Awaiting approval`, `Previous` and `Rejected changes` to administrators.
- Keep configuration revision identifiers, states, expected revisions and
  request pins in the API, database, audit and support evidence.
- Select newly created proposed changes immediately and show configuration
  history by descriptive title, short immutable reference and state, without
  exposing storage-version language.
- Search the locally authorised hierarchy literally by display name, stable code
  or unit kind. Retain matching ancestors so every result has organisational
  context. Search is a presentation projection, never an access-control boundary.
- Show a keyboard-operable root-to-unit breadcrumb for the selected unit.
- Offer only effective, routing-enabled parents of the immediately preceding
  hierarchy kind. Exclude self, the current parent and ineffective units.
- Keep complete server-side hierarchy validation authoritative because a client
  can forge any proposed snapshot.
- Compare proposed changes with their base semantically and canonically. Do not
  report normalisation-only differences or unchanged staffing shortfalls as new
  operator changes.
- Compare every unit and edge checkpoint from the proposal time onwards. Show
  the effective time for each distinct transition so a later scheduled move or
  retirement cannot be approved through an apparently empty preview.
- Bind approval and activation to the same canonical SHA-256 snapshot digest.
  Seal non-Draft configuration components with PostgreSQL triggers and guard
  lifecycle transitions independently of the React client.
- Bind the workflow template to an approved workflow identifier whose core
  process identity, compatibility key, checksum and approval evidence are sealed
  in PostgreSQL. Keep deployment-key and availability changes in the separate
  controlled operator boundary.
- Normalise display names, reject control and bidirectional characters, require
  effective siblings to have distinct names and retain stable codes in paths.
- Preserve independent review, step-up authentication, recorded reasons,
  one-winner concurrency, effective dates, immutable history and in-flight pins.
- Reverse an applied change through new proposed changes. Never delete or edit
  historical configuration.

## Consequences

- Occasional administrators can operate the page without learning the storage
  model, while support and audit retain exact revision evidence.
- Parent filtering prevents common mistakes but does not replace validation or
  authorisation.
- Search remains responsive for the bounded in-memory configuration limit. A
  later server-side index must preserve the same scope, literal matching and
  ancestor-context rules before the client limit is raised.
- Effective-time projection is shared by the hierarchy, breadcrumb and parent
  selector to prevent contradictory views around scheduled moves or retirement.
- The snapshot reference is deliberately technical assurance evidence. It is
  not presented as a user-managed version or draft number.

## Rejected alternatives

- Remove immutable revisions: rejected because it weakens concurrency,
  separation of duties, rollback and in-flight attribution.
- Make the active hierarchy directly editable: rejected because partial changes
  could become routable before complete validation.
- Treat the filtered parent list as authorisation: rejected because browser state
  is attacker-controlled.
- Add fuzzy or recommended routing: rejected because the MVP is human-led and
  the application must not rank or choose destinations.
