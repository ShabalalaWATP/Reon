# ADR 0004: Data-Driven Organisational Routing

## Status

Accepted, 6 August 2026. Staffing baseline amended on 6 August 2026.

## Context

OSG Team, reached through JIOC, DIGOC and NCGI-A Ops, is the MVP's initial
operational team. Every other seeded team is also selectable and must have
synthetic Manager and Analyst staffing so the workflow can prove a real route.

Hard-coding one BPMN branch per unit would become unmaintainable as the service
expands. Silently assigning OSG users to other teams would produce misleading
and unsafe workflow state.

## Decision

- Model JIOC as the single root, with command, Ops-group and delivery-team units
  beneath it.
- Keep stable unit identifiers, parent-child relationships and staffing state in
  product-owned reference data.
- Retire removed reference records from new selection while preserving them for
  historical route reconstruction.
- Make every configured child a first-class routing destination. Do not mark
  public-safe siblings as demonstration-only, visually secondary or disabled.
- Use generic human routing tasks whose selected unit ID determines the next
  candidate group.
- Use shared routing pools for every command and Ops branch. If a selected
  delivery team is unstaffed, create and retain its Camunda manager task and
  expose `Awaiting team staffing`. Do not reassign it to OSG or invent progress.
- Seed every team with at least one active Manager and one active Analyst. OSG
  receives additional people for the operational pilot. Administration may
  subsequently make a team unstaffed, in which case the preceding rule applies.
- Allow only the authorised current routing user to select a direct child of the
  unit in scope. Backend policy remains authoritative.
- After team delivery begins, route approval only from Team Analyst to Team
  Manager and then QC Manager. JIOC, command and Ops users receive tracking
  visibility, not product-approval authority.
- Scope tracking rows in PostgreSQL to the actor's selected root, command or Ops
  membership before returning the metadata-only projection.
- Disseminate an authenticated application-owned plain-text download link. Do
  not fetch arbitrary URLs or accept binary files in this slice.
- Revalidate the selected relationship, actor, role, task, request version and
  candidate group immediately before dispatch.
- Pin started requests to their process and hierarchy versions.

## Consequences

The same workflow can route to many units without one process definition per
team. The alternative-route smoke completes through Beacon Team's own Manager
and Analyst groups. If later account changes leave any team unstaffed, that
route waits visibly instead of borrowing another team's identities.

Tracking views need a separate read-only policy from task ownership. The product
also needs negative tests for crafted unit IDs, skipped levels, cross-scope
tracking and unreleased product access.
