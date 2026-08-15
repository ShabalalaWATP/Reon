# ADR 0033: Shared assigned Analyst authority

## Status

Accepted

## Context

Mist Service stores an accountable Lead Analyst and an append-only roster of
active Lead and Contributor assignments. Camunda user tasks support one technical
assignee, so the application previously treated that assignee as the only person
who could complete production work. This contradicted the intended team model
and hid genuine assignments from additional Analysts.

## Decision

Treat the active request participant roster as the authoritative production
permission set. Keep the Lead in `assigned_specialist_id` and as the Camunda task
assignee for compatibility and accountability display, but do not derive extra
functional authority from that label.

Project one personal action per assigned Analyst and expose the shared task to
each active participant. Reauthorise roster membership, account state, exact-team
membership, route membership, request version, stage and task state at the locked
intent and dispatch boundaries. The first valid completion moves the single
shared task. Later concurrent or stale commands fail closed.

Product packages remain author-owned drafts. Any assigned Analyst may create and
work on their own package, while existing manager and QC separation-of-duty rules
continue to apply.

## Consequences

- Lead and additional Analysts have identical production controls.
- Lead remains an explicit accountability label in ticket and queue views.
- Camunda keeps a single technical assignee without becoming the application
  authorisation source.
- Revocation is controlled by the active participant roster and exact team
  membership, not by cached UI state.
