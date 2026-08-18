# Typed Request and Work Authorisation

## Status

Implementation milestone, 11 August 2026.

## Objective

Make the core request and work-item access rules one explicit, typed domain
policy. Request and work services must ask that policy for a decision instead of
rebuilding combinations of role, ownership, team, stage and assignment checks.
The public permissions and workflow remain unchanged.

This is the second bounded delivery from the SOLID and Secure by Design
improvement programme. It covers the highest-value request-detail and active
work boundaries. Administration, statistics, planning and team-workspace
policies remain separate because they protect different objects and grants.

## Required design

- Define typed request and work operations.
- Return an immutable decision with an internal denial category rather than a
  bare Boolean from the new policy entry points.
- Keep policy code independent of FastAPI, SQLAlchemy and Camunda.
- Preserve small Boolean compatibility functions where existing callers still
  need them, but derive them from the typed policy.
- Make `RequestService` use typed decisions for creation, listing, detail,
  cancellation, feedback, product download and field disclosure.
- Make `WorkService` use typed decisions for visibility, claiming, completion,
  specialist selection and routing-option access.
- Retain database-scoped lookups as defence in depth. A service policy decision
  must not replace query-level object filtering.

## Denial behaviour

An unauthorised caller must receive the same concealed `404 NOT_FOUND` response
for a real direct identifier as for an unknown identifier. The response must not
reveal whether denial was caused by role, ownership, route, team or assignment.

An authorised actor who owns the active work item but submits an action that is
not valid for its current workflow state continues to receive the existing
conflict response. Authorisation refactoring must not turn workflow conflicts
into existence or permission disclosures.

## Denial matrix

| Object/action | Allowed context | Required denials |
| --- | --- | --- |
| Create or list customer requests | Customer account | Every staff and platform role |
| View request detail | Owning Customer, active assigned routing user, exact assigned Team Manager, assigned Lead or additional Team Analyst | Other Customer, platform support, unassigned colleague, sibling route or sibling team |
| Cancel request | Owning Customer | Other Customer and every staff role |
| Submit feedback | Owning Customer after completion | Other Customer and every staff role; valid owner before completion receives the existing conflict |
| Download customer product | Owning Customer with a released product | Other Customer and every staff role |
| View unreleased product content | Authorised staff request viewer | Customer |
| View clarification content | Owning Customer, assigned Analyst or exact Team Manager | Other authorised routing roles |
| View active work | Exact current role and object scope; open shared work or individually assigned work as applicable | Wrong role, wrong stage, sibling route/team, unassigned colleague and platform support |
| Claim work | Exact current shared decision role and object scope | Customers, Analysts, wrong role/scope and already-owned work |
| Complete work | Current assignee, exact role/scope and allowed action | Every other actor; invalid action by the current assignee remains a conflict |
| List eligible Analysts | Exact Team Manager on visible delivery-planning work | Other roles, sibling Manager and inaccessible identifier |
| View routing options | Current authorised routing user at a routing stage | Customer, delivery roles, sibling route and inaccessible identifier |

## Acceptance criteria

1. Request and work services use typed policy decisions for the operations in
   scope.
2. The policy module has no FastAPI, SQLAlchemy or Camunda imports.
3. Unit matrices cover every representative role and both matching and
   mismatching ownership, team and assignment.
4. Public API tests prove cross-role, cross-route and direct-identifier
   concealment, including identical unknown and forbidden responses.
5. Existing workflow-state conflict responses remain unchanged.
6. Backend line and branch coverage remain at or above 95 per cent.
7. Architecture and threat-model documentation describe both policy and
   database-query enforcement.

## Out of scope

- Changing representative roles, organisation routes or Camunda candidate
  groups.
- Granting Platform Administrators request-content access.
- Replacing the separate administration, statistics, planning or workspace
  grant models.
- Changing HTTP status codes or public error bodies.
