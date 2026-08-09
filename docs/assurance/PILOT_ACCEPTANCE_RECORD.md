# Pilot acceptance record

> Historical MVP acceptance template. Product Evolution has a separate
> acceptance record and remains unsigned.

## Status

Prepared on 7 August 2026. This record is ready for named stakeholder review but
is not signed. Blank names or decisions mean the corresponding gate remains
open. Technical evidence cannot self-approve product, security, operations or
representative-user acceptance.

## Candidate baseline

| Item | Candidate |
| --- | --- |
| Application | ISTARI Service local test MVP |
| Frontend | React production image |
| API | FastAPI production image |
| Database | PostgreSQL 17.9 |
| Workflow | Camunda 8.9.14 |
| Information boundary | Synthetic, public-safe test data only |
| Baseline decisions | `docs/decisions/PILOT_BASELINE_DECISIONS.md` |
| Final completion audit | `docs/assurance/FINAL_COMPLETION_AUDIT.md` |

## Technical evidence presented

| Area | Evidence | Result for review |
| --- | --- | --- |
| Customer, routing, clarification, production and release | Browser traces plus final HTML/JUnit report | Evidence ready |
| Mandatory data quality and feedback | Cross-browser form and completed-request journeys | Evidence ready |
| Organisation, teams and accounts | Organisation and routing directory plus seed invariants | Evidence ready |
| Scoped statistics | Cross-branch oracle, chart/table review and management-grant tests | Evidence ready |
| Roster, calendar and agile workspace | API/concurrency matrix and Manager browser traces | Evidence ready |
| Security and privacy | Threat models, abuse matrix, dependency, static, secret and image scans | Evidence ready |
| Accessibility and compatibility | Axe, keyboard, focus, narrow-width and Chrome/Edge/Firefox evidence | Evidence ready |
| Performance | 250 users, 5,000 occurrences, 2,500 packages and 50 concurrent users | Evidence ready |
| Backup and recovery | Clean restore and controlled database/Camunda interruption rehearsals | Evidence ready |

## Representative-user scenarios

The named participants should execute or review these scenarios against the
candidate baseline and record the result without entering real information.

| ID | Representative | Scenario | Expected result | Result | Evidence or comment |
| --- | --- | --- | --- | --- | --- |
| UAT-01 | Customer | Submit every required field and track the request | Request is visible with current status and immutable history |  |  |
| UAT-02 | Routing user | Route through a configured command and Ops group | Only valid direct children are selectable and no approval is added |  |  |
| UAT-03 | Team Manager | Assign the selected team's Analyst | Work appears only to that Analyst and workload updates |  |  |
| UAT-04 | Team Analyst and Customer | Ask for and answer additional information | The thread is retained and returns to the same Analyst |  |  |
| UAT-05 | Analyst, Manager and QC | Submit, review, approve and disseminate a product | Separation of duties is visible and the Customer receives a download |  |  |
| UAT-06 | Customer | Download the product and give rating and comments | Download is authenticated and feedback can be sent once |  |  |
| UAT-07 | Scoped manager | Review statistics | Charts and tables contain the authorised organisation only |  |  |
| UAT-08 | Team Manager | Review People, Calendar, Board and Planning | Shared team work is usable and unsafe member removal is blocked |  |  |
| UAT-09 | Platform Administrator | Review accounts and a safe user-lifecycle change | Administration works without access to request content |  |  |

## Known boundaries presented for acceptance

- Local passwords and unauthenticated loopback Camunda are local/test only.
- The candidate contains synthetic information only and is not authorised for
  production or operational data.
- Binary attachments, external notifications and automatic routing are outside
  the MVP.
- Production identity, hosting, networking, secrets, licensing, monitoring and
  penetration testing remain production-readiness work.
- A reviewed Git baseline and private remote or signed local-only exception are
  required separately.

## Decisions and sign-off

| Gate | Decision owner | Named person | Decision (`ACCEPT`, `REJECT`, `CONDITIONAL`) | Date | Conditions or evidence reference |
| --- | --- | --- | --- | --- | --- |
| DOD-50 Product | Product owner |  |  |  |  |
| DOD-51 Security | Security owner |  |  |  |  |
| DOD-52 Operations | Operational owner |  |  |  |  |
| DOD-53 Representative users | UAT lead |  |  |  |  |

Final DOD-54 acceptance may be recorded only after DOD-00, DOD-01, DOD-43 and
DOD-50 to DOD-53 are accepted and the completion audit is refreshed.
