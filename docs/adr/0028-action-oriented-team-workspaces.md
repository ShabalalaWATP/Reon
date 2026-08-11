# ADR 0028: Action-oriented team workspaces

## Status

Accepted, 10 August 2026.

## Context

The organisation workspace already exposes Board, Planning, Calendar, People,
Statistics and Handover capabilities. The overview is primarily a metric strip,
however, and the Board displays eleven lifecycle columns using only the current
cursor page. This makes the workspace feature-rich but weak as a daily operating
surface. It can also make column load appear lower than the complete filtered
result.

## Decision

Make Overview the action-oriented team home. Compose its signals from existing
authorised workspace, planning, calendar, queue and collaboration projections.
Retain Statistics as the deeper analytical surface.

Return complete filtered column aggregates separately from paginated board items.
Show the active delivery flow by default, with exception/downstream and terminal
states progressively disclosed. Add one shared inspector for board and table
selection. Work-package moves remain explicit application commands; request-stage
changes continue through named Camunda human actions only.

Keep routing-unit workspaces queue-led. They receive decision, ageing, handover and
calendar signals, not delivery planning or allocation controls.

Add bounded, self-declared operational skill labels to personal profiles and the
authorised exact-team people projection. Skills have no level, score or automatic
assignment behaviour.

## Consequences

- Board column headers remain truthful regardless of cursor position.
- The normal delivery flow fits a common desktop viewport and terminal history no
  longer dominates it.
- Existing planning capabilities become discoverable without duplicating their
  persistence or policy.
- The overview performs several parallel scoped reads. Query keys and bounded
  responses must permit caching, and pilot performance evidence must cover the
  composed page.
- Inspector access is no broader than the existing request and package endpoints.
- Skill labels remain an aid to human allocation, not a performance measure.
