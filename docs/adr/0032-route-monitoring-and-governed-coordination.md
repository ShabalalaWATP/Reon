# ADR 0032: Route monitoring and governed coordination

## Status

Accepted

## Context

Routing units need continuing situational awareness after handing work onwards.
Treating monitored work as actionable work would blur accountability and could
let a previous handler override the current owner. The existing production
clarification loop is deliberately workflow-blocking and restricted to the
assigned Analyst, so it is not a suitable general conversation mechanism.

## Decision

Keep action and monitoring projections separate. Monitoring access derives only
from exact membership of a unit stored in the immutable request route. Expose
the existing hash-linked request events as the authoritative journey history.

Introduce append-only coordination messages for non-blocking questions and
information. Address them to either the Customer or current owner, authorise
every read and write against current request state, and emit content-minimised
notifications plus request events.

Represent upstream return as an append-only request addressed to the current
owner. Fulfilment uses the existing explicit, adjacent workflow return controls,
which can move SSG Team to ACSA-B Ops, ACSA-B Ops to JOCK and JOCK to CRIOC.
Route membership alone never grants transfer or work-completion authority.

## Consequences

- Routing users gain visibility without gaining implicit control.
- General coordination remains separate from blocking Analyst clarification.
- Returning several stages requires accountable decisions at each routing layer;
  a future direct-return transition would require separate BPMN and fake-engine
  design and testing.
- Message and return records require retention, export and security treatment
  equivalent to request content.
