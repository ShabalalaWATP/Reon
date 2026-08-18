# Assurance record index

Last reviewed: 18 August 2026

This folder contains both living completion authorities and evidence captured
against earlier candidates. A dated pass remains evidence for that candidate
only. It does not become a pass for later source, images, browsers or connected
environments. The Definition of Done matrix and acceptance record determine the
current gate state.

| Record | Authority and date | How to use it |
| --- | --- | --- |
| [Acceptance record](ACCEPTANCE_RECORD.md) | Current acceptance authority, unsigned | Records candidate identity, representative scenarios and named decisions. `PENDING` is not acceptance |
| [Definition of Done matrix](DEFINITION_OF_DONE_MATRIX.md) | Current completion authority | Single source for `OPEN`, `IN PROGRESS`, `EVIDENCE READY` and `ACCEPTED` gate states |
| [Specification traceability](SPECIFICATION_TRACEABILITY.md) | Current traceability authority, updated 18 August 2026 | Maps implemented capabilities to specifications, ADRs and living threat models |
| [Accessibility evidence](ACCESSIBILITY_EVIDENCE.md) | Current control description with latest recorded browser review on 10 August 2026 | Supports technical accessibility gates; formal conformance and named reviewer acceptance remain open |
| [Browser and workflow evidence](BROWSER_AND_WORKFLOW_EVIDENCE.md) | Mixed dated journeys from 7, 10 and 14 August 2026 plus current screenshot artefacts | Use each result only with its stated candidate and browser context; screenshots do not close acceptance |
| [Configuration and routing evidence](CONFIGURATION_AND_ROUTING_EVIDENCE.md) | Working-tree evidence record created 9 August 2026, not accepted | Retains its original test counts, revision and missing-evidence list; it is not the current regression total |
| [Final completion audit](FINAL_COMPLETION_AUDIT.md) | Dated local baseline audit, 7 August 2026 | Historical requirement audit. Follow the current Definition of Done matrix for open gates |
| [Log data-minimisation evidence](LOG_DATA_MINIMISATION_EVIDENCE.md) | Dated container capture, 7 August 2026 | Evidence for the captured image and journey only; formal security-owner review remains separate |
| [Migration and restore evidence](MIGRATION_AND_RESTORE_EVIDENCE.md) | Current-head review on 17 August 2026 plus older dated rehearsals | Distinguishes the current `0049_legacy_product_cleanup` migration proof from earlier revision evidence |
| [Performance evidence](PERFORMANCE_EVIDENCE.md) | Dated local runs from 7 and 8 August 2026 | Does not establish current search, managed-product, notification or recovery performance |
| [Recovery evidence](RECOVERY_EVIDENCE.md) | Current automated worker/analytics verification on 18 August 2026 plus dated live interruption rehearsals | Automated repair checks do not replace target-scale rebuild, joined restore or disaster-recovery rehearsal |
| [Security matrix evidence](SECURITY_MATRIX_EVIDENCE.md) | Current source supplement on 18 August 2026 plus historical 7 August baseline | Supports server-side policy review while external testing and security-owner acceptance remain open |
| [Security scan evidence](SECURITY_SCAN_EVIDENCE.md) | Current source and regression summary on 18 August 2026 with separately dated scan records | Do not treat older CodeQL, secret, image or DAST results as rerun for the current candidate |
| [SOLID and Secure by Design review](SOLID_SECURE_BY_DESIGN_REVIEW.md) | Current maintainability addendum on 18 August 2026 plus dated 11 August review | Internal architecture and security assessment, not penetration testing or production accreditation |
| [Source-control baseline](SOURCE_CONTROL_BASELINE.md) | Dated baseline evidence, 7 August 2026 | Retains the reviewed commit, history-scan and remote evidence for that baseline |

Production use remains blocked until every applicable current gate has the
required immutable evidence and named acceptance.
