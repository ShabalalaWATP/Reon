# Expanded-capability acceptance record

Status: prepared for review, not signed
Candidate: uncommitted local working tree reviewed on 8 August 2026

## Acceptance rule

Technical evidence cannot self-approve the release. Every applicable
expanded-capability Definition of Done gate must be accepted against an immutable commit
and reproducible evidence before production use.

## Scope presented for acceptance

- role-scoped personal work and notifications;
- managed PDF, DOCX and PPTX products or approved HTTPS links;
- effective scheduled organisation and bounded workflow configuration;
- guided current/proposed configuration administration;
- planning enhancements and exactly scoped statistics; and
- security, accessibility, recovery and operational controls supporting them.

Routing-user path confirmation and literal direct-child name/code search are
implemented in the native routing control. Automated evidence does not replace
representative-user acceptance of those controls.

## Representative UAT scenarios

Every result must name the tester, environment, immutable revision and linked
issue. `PENDING` is not acceptance.

| Scenario | Representative | Expected result | Actual/evidence | Issue |
|---|---|---|---|---|
| CAU-01 search and ancestor context | Platform Administrator | Name, code and kind search retains authorised ancestors | PENDING | PENDING |
| CAU-02 keyboard breadcrumb | Platform Administrator | Root-to-selection path is operable and announced | PENDING | PENDING |
| CAU-03/04 create and move | Platform Administrator | Only effective exact-kind parents appear; forged or stale saves fail | PENDING | PENDING |
| CAU-05 task language | Platform Administrator | Current/proposed language works without persistence jargon | PENDING | PENDING |
| CAU-06 independent review | Two Platform Administrators | Creator cannot approve; exact reviewed snapshot activates | PENDING | PENDING |
| CAU-07 pinning | Routing User and Customer | Current and in-flight requests retain the correct configuration | PENDING | PENDING |
| CAU-08 conflict/recovery | Platform Administrator and Support | Stale writes fail safely and current state restores | PENDING | PENDING |
| HRU-01/04/05 route selection | CRIOC, Command and Ops users | Every authorised sibling, including unstaffed teams, is human-selectable; stale choices fail | PENDING | PENDING |
| HRU-02 route breadcrumb | Routing User | Selected root-to-stage path and chosen destination are announced before hand-off | PENDING | PENDING |
| HRU-03 destination search | Routing User | Literal name/code search remains inside every server-authorised direct child | PENDING | PENDING |
| HRU-06 competing claim | Two eligible Routing Users | Exactly one claim and outcome wins | PENDING | PENDING |
| HRU-07 clarification | Customer and assigned Analyst | Stored scoped thread returns to the named stage | PENDING | PENDING |
| HRU-08 tracking-only access | CRIOC, Command and Ops trackers | Selected path sees metadata, never approval or protected content | PENDING | PENDING |
| Managed product release | Analyst, Manager, QC and Customer | Immutable managed file or approved link is reviewed, released and accessed in-dashboard | PENDING | PENDING |
| Negative permission matrix | All representative roles | Cross-scope and direct-identifier access is denied without disclosure | PENDING | PENDING |

## Sign-off

| Authority | Named person | Decision | Date | Conditions or evidence reference |
|---|---|---|---|---|
| Product Owner | PENDING | PENDING | PENDING | PE-DOD-70 |
| Security Owner | PENDING | PENDING | PENDING | PE-DOD-71 |
| Operational Owner | PENDING | PENDING | PENDING | PE-DOD-72 |
| Data/Privacy Owner | PENDING | PENDING | PENDING | Classification, retention and privacy decisions |
| CRIOC representative | PENDING | PENDING | PENDING | Applicable routing, tracking and statistics UAT |
| Command/Ops representative | PENDING | PENDING | PENDING | Applicable routing, tracking and statistics UAT |
| Team Manager representative | PENDING | PENDING | PENDING | Assignment, review, planning and staffing UAT |
| Analyst representative | PENDING | PENDING | PENDING | Work, clarification and product-package UAT |
| QC representative | PENDING | PENDING | PENDING | Review and dissemination UAT |
| Customer representative | PENDING | PENDING | PENDING | Form, tracking, clarification, download/link and feedback UAT |
| Platform Administrator | PENDING | PENDING | PENDING | Configuration and safe identity administration UAT |

## Open acceptance evidence

- immutable commit, hosted CI and signed release inventory;
- supported-browser, keyboard, narrow-width, zoom and manual accessibility review;
- representative and target-topology Camunda sibling routing, plus production
  PostgreSQL activation and HA concurrency acceptance;
- target object-store and malware-scanner operation;
- accepted load, monitoring, recovery and multi-store reconciliation evidence;
- production identity, hosting, data handling and operational ownership; and
- requirement-by-requirement close-out of the expanded-capability DoD matrix.

Blank or pending fields mean not accepted. Conditions must identify an owner,
due date and risk expiry. This record must not be pre-populated by the delivery
team on behalf of an accountable owner.
