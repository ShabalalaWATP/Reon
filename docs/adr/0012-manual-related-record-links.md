# ADR 0012: Manual Related-Record Links

## Status

Accepted locally for the MVP.

## Context

JIOC intake needs to record possible duplication or related work without adding
automated recommendations, exposing broad content or allowing the board to alter
workflow state.

## Decision

Store an append-only typed relationship from the current service request to
another authorised request. Candidate search is a bounded PostgreSQL query over
reference and title and is available only to the actor who owns the active JIOC
task. It uses the existing organisation-route membership as the scope boundary.

Relationship creation is a separate application command. It locks the current
task and source request, revalidates actor and membership, requires an optimistic
source version, validates the target in the same scope and appends a hash-linked
request event in the transaction. It does not call Camunda because it does not
move process position.

## Consequences

- Human decisions and their reasons are reconstructable without treating a link
  as truth.
- Search remains deliberately small and cannot inspect narrative or product
  content.
- Existing-output candidates depend on an application-owned released-product
  record, never an analyst-supplied URL.
- A future external search or similarity service requires a separate ADR and
  threat model.
