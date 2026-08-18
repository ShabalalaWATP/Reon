# Mist Service acceptance record

Status: prepared for review, not signed
Last reviewed: 18 August 2026

This is the single current product, security, operational, accessibility and
representative-user acceptance record. It must be bound to an immutable release
candidate before anyone signs it. Blank or `PENDING` fields mean that acceptance
has not been given.

## Acceptance rule

Technical evidence cannot approve the service on behalf of an accountable
owner. Every applicable gate in the
[Definition of Done matrix](DEFINITION_OF_DONE_MATRIX.md) must be `ACCEPTED`
against current, reproducible evidence before production use.

The supporting authorities are:

- [final completion audit](FINAL_COMPLETION_AUDIT.md);
- [current security scan evidence](SECURITY_SCAN_EVIDENCE.md) and the dated
  [Codex Security remediation matrix](../security/CODEX_SECURITY_REMEDIATION_MATRIX_2026-08-17.md);
- [accessibility and WCAG 2.2 evidence](ACCESSIBILITY_EVIDENCE.md);
- [enterprise readiness gap register](../ENTERPRISE_READINESS_GAP_REGISTER.md);
- [production gates](../deployment/PRODUCTION_GATES.md); and
- [pilot baseline decisions](../decisions/PILOT_BASELINE_DECISIONS.md).

## Candidate baseline

Complete this table before representative testing begins.

| Item | Candidate |
| --- | --- |
| Application | Mist Service |
| Git revision | PENDING immutable commit |
| Candidate build or image identifiers | PENDING |
| Test environment and date | PENDING |
| Frontend | React production build |
| API | FastAPI production build |
| Database | PostgreSQL 17 |
| Workflow | Camunda 8.9.14 |
| Supported browsers tested | PENDING |
| Information boundary | Synthetic, public-safe test data only |

Changing the application revision, migration head, workflow model or material
runtime configuration invalidates results unless the reviewer records why the
change cannot affect their decision.

## Scope presented for acceptance

- mandatory Customer submission, tracking, cancellation, clarification,
  released-product access and feedback;
- human-led routing through JIOC, DIGOC, NCGI-A Ops, OSG Team and selectable
  sibling branches;
- Manager assignment of one Lead Analyst and multiple Contributors;
- Analyst production, Manager review, independent QC release and reasoned
  rework;
- role-scoped personal actions, notifications, team workspaces and calendars;
- managed PDF, DOCX and PPTX products or approved HTTPS links;
- effective-dated organisation, roster and bounded workflow configuration;
- content-minimised, descendant-scoped operational statistics;
- platform administration without implicit request-content access; and
- security, accessibility, recovery and operational controls supporting those
  capabilities.

## Representative-user scenarios

Each result must name the tester, environment, candidate revision, result and
linked defect where applicable. `PENDING` is not acceptance.

| ID | Representative | Scenario and expected result | Result and evidence | Issue |
| --- | --- | --- | --- | --- |
| UAT-01 | Customer | Submit every mandatory field and see the request, title, status and immutable progress history in My requests | PENDING | PENDING |
| UAT-02 | Customer | Cancel an eligible request with a reason and see the request close with relevant parties notified | PENDING | PENDING |
| UAT-03 | Customer and assigned Analyst | Exchange one or more additional-information messages in the dashboard and return work to the same Analyst assignment | PENDING | PENDING |
| UAT-04 | JIOC routing user | Claim a new routing decision, inspect authorised context and select DIGOC without approving the request | PENDING | PENDING |
| UAT-05 | DIGOC and NCGI-A Ops routing users | Route to the next direct child while retaining lifecycle tracking and without adding approval stages | PENDING | PENDING |
| UAT-06 | Routing users on sibling branches | Select and complete a configured sibling route while remaining unable to view sibling records | PENDING | PENDING |
| UAT-07 | OSG Team Manager | Assign one accountable Lead and multiple additional Analysts; Analysts cannot claim unassigned team work themselves | PENDING | PENDING |
| UAT-08 | Assigned Analysts | Collaborate and use the same production controls while the Lead remains visibly accountable | PENDING | PENDING |
| UAT-09 | Team Manager and QC reviewer | Review an immutable product revision, request reasoned changes where needed and prevent self-approval | PENDING | PENDING |
| UAT-10 | Separate QC releaser and Customer | Release an approved file or link, enforce a different QC reviewer and releaser, and confirm only the authorised Customer can access it | PENDING | PENDING |
| UAT-11 | Customer | Download the released product and submit one rating with optional feedback comments | PENDING | PENDING |
| UAT-12 | Team Manager | Sort the People register, add or schedule an eligible membership change and remain blocked from unsafe removal | PENDING | PENDING |
| UAT-13 | Manager and Analyst | Use personal and shared calendars; visible personal events appear to the team while private details show only as Busy | PENDING | PENDING |
| UAT-14 | Team users | Use the Service Request board, table, Work Package board and Activity without requiring a drag gesture or changing Camunda outside named actions | PENDING | PENDING |
| UAT-15 | JIOC, DIGOC, NCGI-A Ops and team managers | See statistics for their own scope and descendants, never ancestors or sibling branches | PENDING | PENDING |
| UAT-16 | Platform Administrator | Create and manage accounts and teams, use configuration search and breadcrumbs, and remain outside request content | PENDING | PENDING |
| UAT-17 | All representative roles | Attempt copied identifiers and cross-scope actions; the service denies access without confirming inaccessible records exist | PENDING | PENDING |
| UAT-18 | Support and operational owner | Recover controlled PostgreSQL, Camunda, outbox and projection interruptions without invented success or duplicate work | PENDING | PENDING |

## Accessibility acceptance

Technical results are recorded in the
[accessibility evidence](ACCESSIBILITY_EVIDENCE.md). Named reviewers must still
complete the following against the immutable candidate:

| ID | Reviewer | Review | Result and evidence | Issue |
| --- | --- | --- | --- | --- |
| A11Y-01 | Keyboard user | Complete every critical role journey without a pointer, with logical order, visible focus and no trap | PENDING | PENDING |
| A11Y-02 | Screen-reader reviewer | Complete supported journeys with NVDA and Chrome or Edge; add JAWS or VoiceOver where the support matrix requires them | PENDING | PENDING |
| A11Y-03 | Low-vision reviewer | Review 200 and 400 per cent zoom, text spacing, 320-pixel reflow, forced colours and focus not obscured | PENDING | PENDING |
| A11Y-04 | Representative users | Review plain language, error recovery, status comprehension and cognitive load | PENDING | PENDING |

No row may be marked accepted solely because axe, component or contrast tests
passed.

## Sign-off

| Authority | Named person | Decision | Date | Conditions, owner, due date and evidence |
| --- | --- | --- | --- | --- |
| Product Owner | PENDING | PENDING | PENDING | PENDING |
| Security Owner | PENDING | PENDING | PENDING | PENDING |
| Operational Owner | PENDING | PENDING | PENDING | PENDING |
| Data and Privacy Owner | PENDING | PENDING | PENDING | PENDING |
| Accessibility Reviewer | PENDING | PENDING | PENDING | PENDING |
| JIOC representative | PENDING | PENDING | PENDING | PENDING |
| DIGOC or sibling command representative | PENDING | PENDING | PENDING | PENDING |
| NCGI-A Ops or sibling Ops representative | PENDING | PENDING | PENDING | PENDING |
| Team Manager representative | PENDING | PENDING | PENDING | PENDING |
| Analyst representative | PENDING | PENDING | PENDING | PENDING |
| QC representative | PENDING | PENDING | PENDING | PENDING |
| Customer representative | PENDING | PENDING | PENDING | PENDING |
| Platform Administrator | PENDING | PENDING | PENDING | PENDING |

Allowed decisions are `ACCEPT`, `REJECT` and `CONDITIONAL`. A conditional
decision must identify the condition, accountable owner, due date and risk
expiry. Delivery staff must not pre-populate an accountable owner's decision.

## Open evidence before sign-off

- immutable release commit, hosted CI and signed release inventory;
- supported-browser and representative-user results recorded above;
- completed manual accessibility review;
- target object-store and malware-scanner operation;
- approved semantic CDR and deployment-wide scanner-capacity evidence;
- current hosted CodeQL, image, authorised staging DAST and any required
  independent penetration evidence;
- accepted load, monitoring, recovery and multi-store reconciliation evidence;
- target-scale notification-worker and analytics rebuild/replay rehearsal;
- production identity, hosting, data handling and operational ownership; and
- requirement-by-requirement close-out of the Definition of Done matrix.
