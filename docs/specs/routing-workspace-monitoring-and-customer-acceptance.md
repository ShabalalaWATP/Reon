# Routing workspace monitoring and Customer acceptance

Status: implemented and assured locally, 13 August 2026.

The implemented
[structured conversations, packages and contexts](structured-conversations-packages-and-contexts.md)
amendment does not change the meaning of dissemination, access, acceptance or
feedback defined here. It adds bounded conversation and actor-context rules
around those existing records.

## Problem addressed

Routing workspaces previously showed only open human tasks. After a unit routed
a request onwards, the request disappeared from that workspace even though its
members retained exact-route monitoring access. The implementation separates
actionable work, active monitored work and completed history because only the
first category grants workflow authority.

Dissemination previously recorded delivery and completed the workflow without
recording whether the originating Customer accepted the product. The explicit
acceptance action remains separate from opening an artefact or submitting
feedback.

## Behaviour

1. Every routing-unit queue leads with `Needs routing action` and contains only
   current Camunda-backed work available or assigned to that exact unit.
2. `Active requests routed onwards` contains exact-route requests that have no
   current work item in the unit and have not reached Customer acceptance or a
   non-delivery terminal state.
3. `Completed requests` contains Customer-accepted managed-product requests and
   requests cancelled or closed without delivery. Legacy completed requests,
   which have no managed dissemination requiring acceptance, remain completed.
4. Active monitoring and completed history are separate native disclosure
   sections, collapsed by default. Their summaries state scope and item count.
5. Monitored rows show reference, title, status, current owner, required date,
   age and an explicit link to the read-only tracked-request detail.
6. Both passive sections use the existing exact route-unit tracking filter and
   never add claim, completion, transfer or product access controls.
7. A disseminated managed product exposes an explicit `Accept product` action
   only to its active originating Customer. Acceptance is idempotent, stored on
   the dissemination record and appended to the ticket history.
8. Link opening, managed-file download and feedback remain separate audited
   interactions and never imply acceptance.
9. Approved external HTTPS links remain valid service-product artefacts. QC
   attestation, authenticated redirect, expiry, withdrawal and allow-list
   controls continue to apply.

## Acceptance criteria

- JIOC, DIGOC and NCGI-A Ops can distinguish work they must action from active
  requests already routed onwards.
- Passive active and completed sections are closed on initial render and can be
  opened independently with keyboard or pointer input.
- A request currently actionable in the unit is not duplicated in passive
  monitoring.
- A managed request remains in active monitoring after dissemination until the
  originating Customer explicitly accepts it.
- Customer acceptance appears in the immutable ticket history with actor and
  timestamp, and a replay cannot create a second event.
- A sibling route member, another Customer or a Platform Administrator cannot
  discover or record the acceptance.
- Frontend and backend line and branch coverage remain at least 95 per cent.

## Non-goals

- Granting workflow authority through a monitoring row.
- Treating feedback score, product download or external-link opening as
  acceptance.
- Allowing routing users to view product content or direct external destinations.
- Reopening the completed Camunda process when Customer acceptance is recorded.
