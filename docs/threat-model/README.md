# Threat-model index

Last reviewed: 18 August 2026

These are living risk and control authorities for the current synthetic service.
They define required abuse-case evidence and residual gates, but do not by
themselves prove that a test, scan, rehearsal or acceptance has occurred. Use the
[assurance index](../assurance/README.md) and
[Definition of Done matrix](../assurance/DEFINITION_OF_DONE_MATRIX.md) for
evidence state.

| Threat model | Current scope |
| --- | --- |
| [Service request workflow](service-request-workflow.md) | Intake, sessions and context, human routing, conversations, managed products, QC separation, dissemination and migration integrity |
| [Platform administration](platform-administration.md) | Identity and organisation metadata, step-up credential rotation, configuration lifecycle and denial of request-content access |
| [Team workspaces and calendars](team-workspaces-and-calendars.md) | Membership, grants, colleague profiles, calendars, boards, packages, planning, hasteners and exact-team object access |
| [Management and analytics](management-and-analytics.md) | Action-scoped reporting, content-free facts, definition integrity, bounded rebuild/replay, suppression and export controls |
| [Operations and recovery](operations-and-recovery.md) | Audit keys, retention, backup, restore, worker fencing, notification repair, analytics recovery, supply chain and runtime topology |

Cross-cutting production blockers include approved connected identity, private
storage and semantic CDR, deployment-wide scanner admission, authenticated
Camunda, independent audit enforcement, joined recovery, target-environment
security assessment and named acceptance.
