# ADR 0004: Data-Driven Organisational Routing

## Status

Accepted, 6 August 2026. Current decision reviewed on 10 August 2026.

## Context

SSG Team, reached through CRIOC, JOCK and ACSA-B Ops, is the MVP's initial
operational team. Every other seeded team is also selectable and must have
synthetic Manager and Analyst staffing so the workflow can prove a real route.

Hard-coding one BPMN branch per unit would become unmaintainable as the service
expands. Silently assigning SSG users to other teams would produce misleading
and unsafe workflow state.

## Decision

- Model CRIOC as the single root, with command, Ops-group and delivery-team units
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
  expose `Awaiting team staffing`. Do not reassign it to SSG or invent progress.
- Seed every team with at least one active Manager and one active Analyst. SSG
  receives additional people for the operational pilot. Administration may
  subsequently make a team unstaffed, in which case the preceding rule applies.
- Allow only the authorised current routing user to select a direct child of the
  unit in scope. Backend policy remains authoritative.
- After team delivery begins, route approval only from Team Analyst to Team
  Manager and then QC Manager. CRIOC, command and Ops users receive tracking
  visibility, not product-approval authority.
- Scope every tracking list and detail query in PostgreSQL to exact membership
  of the request's selected CRIOC, command or Ops route before returning data.
- Show title, reference, current ownership, selected route and lifecycle in the
  register. Permit an authorised route member to reopen only the original
  submitted request through a dedicated read-only contract. Exclude actions,
  clarifications, feedback and all product content or release links.
- Disseminate an authenticated managed PDF, DOCX or PPTX file, or an approved
  HTTPS product link. Reauthorise every download and redirect at access time.
- Revalidate the selected relationship, actor, role, task, request version and
  candidate group immediately before dispatch.
- Pin started requests to their process and hierarchy versions.

## Consequences

The same workflow can route to many units without one process definition per
team. The alternative-route smoke completes through Beacon Team's own Manager
and Analyst groups. If later account changes leave any team unstaffed, that
route waits visibly instead of borrowing another team's identities.

Tracking views use a separate read-only policy and response contract from task
ownership and operational request detail. The product also needs negative tests
for crafted unit IDs, skipped levels, direct cross-scope identifiers and
unreleased product access.
