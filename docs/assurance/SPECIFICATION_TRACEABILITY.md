# Specification, decision and threat traceability

Recorded on 7 August 2026. Each implemented capability is mapped to its accepted
Markdown specification, expensive-to-reverse decision record and current threat
model. Shared foundation records apply where a feature uses an existing boundary
rather than creating a new architectural decision.

| Capability | Specification | ADR | Threat model |
| --- | --- | --- | --- |
| Customer form, drafts, tracking, release and feedback | `service-request-mvp.md` | 0001, 0002, 0003 | `service-request-workflow.md` |
| Human-led Camunda workflow | `service-request-mvp.md` | 0001, 0003 | `service-request-workflow.md` |
| Organisation tree and selectable routing | `service-request-mvp.md` | 0004 | `service-request-workflow.md` |
| Analyst clarification loop | `service-operations-expansion.md` | 0010 | `service-request-workflow.md` |
| Scoped statistics | `service-operations-expansion.md` | 0006, 0007 | `management-and-analytics.md` |
| Team roster lifecycle | `service-operations-expansion.md` | 0006, 0011 | `team-workspaces-and-calendars.md` |
| Shared and personal calendars | `service-operations-expansion.md` | 0006, 0008 | `team-workspaces-and-calendars.md` |
| Workflow board and agile planning | `service-operations-expansion.md` | 0006, 0009 | `team-workspaces-and-calendars.md` |
| Manual related records | `manual-related-records.md` | 0012 | `service-request-workflow.md` |
| Platform administration | `platform-administration-mvp.md` | 0005, 0013 | `platform-administration.md` |
| Retention, telemetry, backup and recovery | `operational-readiness.md` | 0014 | `operations-and-recovery.md` |

All referenced records exist in `docs/specs`, `docs/adr` and
`docs/threat-model`. The final implementation audit and Definition of Done matrix
remain the aggregate authority for evidence and human acceptance status.
