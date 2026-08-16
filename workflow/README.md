# Service request process contract

`service-request.bpmn` is an executable Camunda 8.9 process containing only
Camunda user tasks. FastAPI remains authoritative for role, hierarchy,
assignment and object-level authorisation. Candidate-group expressions consume
server-computed values. The browser may submit a selected organisational ID,
but it must never submit a candidate-group string.

Each `selected*CandidateGroup` variable is a single-item list containing one
case-sensitive group ID. Camunda requires candidate-group expressions to return
a list of strings. FastAPI derives that list from its server-owned hierarchy.

## Human routing

The direct route is:

1. CRIOC Routing selects a command.
2. The selected command routes directly to one of its Ops functions.
3. The selected Ops function routes directly to one of its teams.
4. The team manager assigns an Analyst.
5. The Analyst submits the work to the same team manager.
6. The manager checks it, QC reviews it, and QC disseminates it to the customer.

CRIOC, command and Ops routing do not form an approval climb after delivery.
Existing return, hold, close and rework decision values remain part of the MVP
process contract.

| Task ID | Label | Assignee | Candidate group |
| --- | --- | --- | --- |
| `intake_review` | CRIOC Routing | None | `crioc-routing` |
| `requester_response` | Provide requested information | `= requesterId` | None |
| `coordination_review` | Request Coordination | None | `= selectedCommandCandidateGroup` |
| `on_hold` | Resolve coordination hold | None | `= selectedCommandCandidateGroup` |
| `allocation_review` | Ops Routing | None | `= selectedOpsCandidateGroup` |
| `delivery_planning` | Team Assignment | None | `= selectedTeamManagerCandidateGroup` |
| `delivery_work` | Product Production | `= assignedSpecialistId` | `= selectedTeamAnalystCandidateGroup` |
| `customer_clarification_response` | Provide production information | `= requesterId` | None |
| `lead_review` | Manager Review | None | `= selectedTeamManagerCandidateGroup` |
| `quality_review` | QC Review | None | `qc-reviewers` |
| `release` | Dissemination | None | `release-managers` |

The `intake_review` label and the `crioc-routing` candidate group keep the
historic CRIOC wording although the unit is now displayed as JIOC. Candidate
groups are stable identifiers, and the BPMN bytes are bound to the approved
workflow definition by checksum, so relabelling the task is a governed
workflow change rather than a display rename. Mist never shows this label;
users see the unit's display name and the "JIOC Routing" owner label.

## Permitted variables

Opaque identity and routing values:

- `requestId`, `requesterId`, `assignedDeliveryTeamId` and
  `assignedSpecialistId`;
- `selectedCommandId` and `selectedCommandCandidateGroup`;
- `selectedOpsId` and `selectedOpsCandidateGroup`;
- `selectedTeamId`, `selectedTeamManagerCandidateGroup` and
  `selectedTeamAnalystCandidateGroup`.

Decision values:

- `intakeDecision`: `request_information`, `progress` or `close`;
- `requesterDecision`: `provide_information` or `withdraw`;
- `coordinationDecision`: `return_to_triage`, `hold`, `close` or
  `send_to_allocation`;
- `holdDecision`: `resume` or `close`;
- `allocationDecision`: `return_to_coordination` or `allocate`;
- `planningDecision`: `return_for_reallocation` or `assign`;
- `deliveryDecision`: `submit` or `request_clarification`;
- `clarificationDecision`: `provide_clarification` or `withdraw`;
- `leadReviewDecision`: `changes_required` or `approve`;
- `qualityDecision`: `changes_required` or `approve`.

Names, request content, form answers, deliverable content, reasons, session
values and CSRF values never belong in Camunda. PostgreSQL owns that data and
the application audit identifies each human action.

## Smoke evidence

The bounded Camunda smoke uses two independent process instances:

1. JOCK → ACSA-B Ops → SSG Team proves the initial operational route through
   Team Manager assignment, directly assigned Analyst production, Manager
   review, QC review, dissemination and process completion.
2. SYGOC → Nimbus Ops → Beacon Team completes through the distinct
   `beacon-team-managers` and `beacon-team-analysts` groups. This proves that a
   selectable sibling team uses its own people and never falls back to SSG.

The first active instance is also started twice with the same business ID, and
the smoke requires Camunda to reject the duplicate with HTTP 409.
