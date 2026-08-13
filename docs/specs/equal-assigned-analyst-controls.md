# Equal assigned Analyst controls

## Problem

A Delivery Manager can assign one Lead Analyst and additional Analysts, but only
the Lead receives the production work item and its controls. Additional Analysts
can see request context elsewhere, yet their personal action view does not make
the assignment clear and the production queue denies workflow actions.

## Required behaviour

- Every active Analyst assignment appears as personal actionable work.
- Every active assigned Analyst can open the production ticket and use the same
  stage controls.
- The Lead Analyst label remains visible as an accountability marker only. It
  grants no additional production capability.
- The queue says whether the signed-in user is the Lead Analyst or an assigned
  Analyst.
- Product drafting and Customer clarification are available to every assigned
  Analyst, subject to the same stage, team and current-membership checks.
- Removing an Analyst from the active roster immediately removes access.
- One shared workflow task remains authoritative. Concurrent or stale outcomes
  continue to produce one winner and reject later attempts.

## Acceptance evidence

- API coverage proves a non-Lead assigned Analyst sees the shared work item with
  the same available actions.
- Policy coverage proves an active non-Lead Analyst can complete production work
  and an unassigned Analyst cannot.
- UI coverage proves the personal queue calls out the assignment, its role and
  the normal production controls.
- The representative workflow continues from Customer intake through QC and
  dissemination.
