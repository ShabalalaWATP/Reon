# Codex Security remediation matrix, 17 August 2026

Status: all findings in the focused review were remediated and verified for the
17 August candidate. Production residual controls remain open.

This is a dated engineering completion record. The later 18 August
maintainability candidate passed its own complete regression and coverage gates.
The later read-only internal review examined the application diff from base
commit `1e7c52ffe7d1649bedaea037470dd40430d2fc6f` through an uncommitted
working tree and found no application security regression within that scope. It
is not immutable release evidence. This record does not claim that hosted
CodeQL, image scanning, DAST or penetration testing was rerun for either
candidate.

| Finding | Implemented control | Verification | Status |
| --- | --- | --- | --- |
| Workspace reads expose data outside the requested action | Action-scoped repository projections and field-level overview redaction apply server-side object and grant policy before schema construction | Projection-security, workspace edge and overview tests | Closed |
| Step-up leaves the pre-elevation bearer valid | Successful step-up atomically rotates opaque bearer and CSRF credentials; secret-free cross-tab reconciliation fetches current session state and rejects stale replacement | Elevation repository, step-up service and browser rotation-race tests | Closed |
| Encoded OOXML active behaviour bypasses superficial inspection | Bounded XML parsing decodes relationship and field semantics and rejects ambiguous archive members before extraction | Adversarial Office semantic and archive preflight tests | Closed |
| PDF active behaviour bypasses superficial byte inspection | Bounded lexical inspection identifies action names outside inert strings, comments and stream bodies without executing or semantically interpreting the document | Adversarial PDF lexical tests | Closed |
| Queued composite scans consume spool storage before concurrency admission | Acquire the composite scan permit before source iteration or first spool and hold it through structural and malware inspection | Composite concurrency and storage-hardening tests | Closed |
| Cancellation leaks transfer resources or performs unsafe compensation | Make pre-promotion cancellation retry-safe, close streamed resources deterministically and avoid destructive compensation after promotion starts | Transfer compensation and cancellation tests | Closed |

## Dated aggregate verification

- Focused backend security and architecture checks passed.
- 1,417 backend tests passed, with 13 environment-specific skips, at 98.77 per
  cent line and 95.17 per cent branch coverage.
- 582 frontend tests passed at 98.79 per cent line and 95.07 per cent branch
  coverage.
- The later 18 August maintainability candidate passed 1,410 backend tests with
  13 environment-specific skips at 98.83 per cent line and 95.10 per cent branch
  coverage, plus 582 frontend tests at 98.80 per cent line and 95.07 per cent
  branch coverage.

## Open production controls

| Control | Reason it remains open | Required evidence |
| --- | --- | --- |
| Approved semantic content disarm and reconstruction | The local OOXML and PDF inspectors are bounded detection controls, not semantic CDR | Selected maintained service or parser, adversarial corpus, assurance ownership and target-environment operation |
| Deployment-wide scanner capacity | The implemented semaphore is per process and does not coordinate every replica | Shared admission control, load and exhaustion tests, monitoring and incident runbook |
| Connected identity and privileged access | Local password step-up and credential rotation do not provide approved OIDC, MFA or enterprise recovery | Identity-provider integration, privileged-access policy and representative security acceptance |
| Independent external assurance | Local and internal reviews are not a penetration test or target-environment DAST assessment | Authorised staging DAST, independent penetration test where required and tracked remediation |

No row in this matrix authorises production use or closes named acceptance in
the [Definition of Done matrix](../assurance/DEFINITION_OF_DONE_MATRIX.md).
