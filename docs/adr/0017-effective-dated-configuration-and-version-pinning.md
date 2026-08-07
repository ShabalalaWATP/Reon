# ADR 0017: Effective-Dated Configuration and Version Pinning

## Status

Accepted for implementation on 7 August 2026. Approver membership and emergency
rollback authority remain named-owner decisions.

## Context

The organisation must add, rename, move and retire valid units without code
changes or loss of history. Workflow variation must remain bounded and cannot
become an application route for arbitrary BPMN, expressions or executable code.
Activating configuration must not silently change in-flight requests.

## Decision

- Store organisation and workflow configuration as immutable versions with
  `Draft`, `Validated`, `Awaiting approval`, `Active`, `Superseded` and `Rejected`
  states. Retain stable unit identifiers, effective-dated names and hierarchy
  edges.
- Validate type and level order, cycles, duplicate identifiers, orphaned units,
  complete Customer-to-team routes, candidate groups, staffing requirements and
  management grants before approval.
- Require a deterministic impact preview, reason, current session-bound step-up
  authentication and approval by a different authorised person before
  activation. An unstaffed valid team remains selectable but exposes `Awaiting
  team staffing`.
- Expose only declarative workflow templates conforming to an allow-listed,
  signed application schema. A template may reference only a compatible BPMN
  definition deployed through the operator-controlled path. It cannot upload
  code, scripts, expressions or arbitrary BPMN, bypass a human stage, grant
  content access or weaken mandatory request fields.
- Atomically select one active configuration snapshot for new requests and pin
  the organisation, form, workflow and notification-policy version identifiers
  at submission.
- Leave in-flight requests on their pinned versions. Any future migration needs a
  separate accepted specification, authorisation model and recovery plan.
- Roll back by activating a validated superseding version. Never destructively
  rewrite a version or its historical request attribution.

The human-led route remains authoritative. Configuration can present permitted
choices and candidate groups, but neither the application nor Camunda chooses a
route, priority, assignee, approval or dissemination recipient.

## Consequences

- Current and as-of behaviour can be reproduced after rename, move, retirement
  and later activation.
- New and in-flight requests may legitimately use different versions, so every
  command, projection and support view must carry and validate version context.
- Configuration activation needs one-winner concurrency, reconciliation and
  superseding-version recovery evidence.
- Compatible BPMN deployment remains an operator responsibility outside the
  administration editor.

## Rejected alternatives

- Edit the active hierarchy in place: historical routes and permissions would be
  ambiguous.
- Migrate all running instances on activation: this changes agreed human work
  without a bounded migration design.
- Provide an arbitrary BPMN editor: it would create an executable administration
  surface and could bypass required human decisions.
