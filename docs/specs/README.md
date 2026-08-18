# Specification index

This directory contains the product, security, operational and engineering
contracts that shaped the current synthetic Mist Service candidate. A
specification describes required behaviour and evidence. Current user behaviour
is summarised in [Current user stories](../USER_STORIES.md), and decision reasons
are retained separately in the [ADR index](../adr/README.md).

Status wording inside each specification remains authoritative. Records that
describe a dated milestone retain that date as delivery history even when later
specifications extend the same area.

## Known current implementation gaps

- Workspace authority returns `PLANNING` and `HANDOVER`, but the current React
  workspace renders neither panel. The current presented workspace contract and
  limitation are recorded in
  [Unified Organisation Workspaces](unified-organisation-workspaces.md).
- The `planning` and `statistics` evolution settings are reported as
  capabilities, but nested router composition leaves their server routes
  registered when the corresponding flag is false. The planning flag is not
  consumed by the current web workspace; the statistics flag hides the web
  route but is not a server-route rollback control. The exact current boundary
  is recorded in the
  [role and permission matrix](../reference/ROLE_PERMISSION_MATRIX.md#known-capability-composition-gaps).

## Product and workflow

- [Structured Service Request Product](service-request-mvp.md): current end-to-end
  request, workflow, route and product contract.
- [Customer intake and account requests](customer-intake-and-account-requests.md):
  Customer briefs, private drafts, profiles and reviewed access requests.
- [Customer cancellation and personal profiles](requester-cancellation-and-personal-profiles.md):
  owner-only cancellation, durable process termination and bounded profiles.
- [Request coordination language and ownership](request-coordination-language-and-ownership.md):
  plain-language queues, claims and accountable owner labels.
- [Route monitoring and coordination](route-monitoring-and-coordination.md):
  exact-route tracking, governed coordination and return requests.
- [Routing workspace monitoring and Customer acceptance](routing-workspace-monitoring-and-customer-acceptance.md):
  actionable, monitored and completed routing views plus post-release acceptance.
- [Equal assigned Analyst controls](equal-assigned-analyst-controls.md): equal
  production authority for the Lead and every additional assigned Analyst.
- [Explainable related-request matching](manual-related-records.md): scoped
  advisory matching and attributable human link decisions.
- [Request and workflow authorisation hardening](request-workflow-authorisation-hardening.md):
  server-owned event audiences and locked participant revalidation.
- [Tracking lifecycle and analytical visuals](tracking-lifecycle-and-analytical-visuals.md):
  read-only route tracking and accessible statistics presentation.
- [Structured conversations, managed packages and bounded contexts](structured-conversations-packages-and-contexts.md):
  conversation audiences, multi-artefact packages, QC separation and dual contexts.
- [Operational Product Capabilities](operational-product-evolution.md): actions,
  notifications, managed dissemination, configuration, planning and statistics.
- [Managed product upload hardening](managed-product-upload-hardening.md): quotas,
  upload intents, image and document validation, scanning and cleanup.

## Identity, navigation and configuration

- [Platform Administration MVP](platform-administration-mvp.md): bounded identity,
  role, membership and safe metadata administration.
- [Configuration administration usability](configuration-administration-usability.md):
  guided immutable configuration proposals, review and activation.
- [Access assistance and global classification marking](access-assistance-and-global-classification.md):
  non-disclosing password assistance and the global visual marking.
- [Authentication and session remediation](authentication-session-remediation.md):
  activity-based sessions, CSRF bootstrap and browser privacy controls.
- [Personalised Overview and Primary Navigation](personalised-overview-and-primary-navigation.md):
  role-aware Home composition and canonical navigation.
- [Action deep links and workspace navigation](action-deep-links-and-workspace-navigation.md):
  safe exact-item links and clear personal, queue and workspace destinations.
- [Operator orientation and service timing](operator-orientation-and-service-timing.md):
  route search, shell orientation and factual elapsed-time signals.
- [Organisation Directory Function Labels](organisation-directory-function-labels.md):
  concise routing, analysis-team and QC directory labels.
- [Hierarchical Operational Overviews](hierarchical-operational-overviews.md):
  role landing pages and descendant-bounded statistics.

## Organisation workspaces and planning

- [Unified Organisation Workspaces](unified-organisation-workspaces.md): shared
  unit workspaces, effective membership, calendars and Analyst assignment.
- [Unified team workspace navigation](simplified-team-workspace-navigation.md): one
  named workspace destination for each current staff unit.
- [Team Operations Workspace](team-operations-workspace-evolution.md): action-led
  team homes, boards, work packages, capacity and planning.
- [Team-visible Personal Calendar Events](team-visible-personal-calendar-events.md):
  default team visibility with deliberate privacy protection.
- [Team noticeboard and pinned links](team-noticeboard-and-pinned-links.md): bounded
  workspace notices and approved reference links.
- [Team member profiles and task hasteners](team-member-profiles-and-task-hasteners.md):
  exact-team professional profiles and staff-only Analyst reminders.

## Security, reliability and operations

- [Operational readiness specification](operational-readiness.md): retention,
  legal holds, backup, restore and content-minimised support controls.
- [Operational telemetry, recovery and supply-chain hardening](operational-telemetry-recovery-and-supply-chain-hardening.md):
  safe access telemetry, runtime images and local recovery topology.
- [Runtime scaling and worker hardening](runtime-scaling-and-worker-hardening.md):
  keyset pagination, fenced worker jobs and target-scale evidence.
- [Workflow runtime reliability remediation](workflow-runtime-reliability-remediation.md):
  synchronous command grace, durable recovery and safe diagnostics.
- [Live QA readiness and primary-route assurance](live-qa-readiness-and-primary-route-assurance.md):
  readiness attestation and maintained primary and sibling journeys.
- [August 2026 security remediation](security-remediation-2026-08.md): container,
  login, scanning, browser and release-gate hardening.
- [Security review remediation, 13 August 2026](security-review-remediation-2026-08-13.md):
  authentication, confidentiality, upload, operations and concurrency invariants.

## Engineering and current-state quality

- [Maintainability and portable evaluation specification](maintainability-and-portable-evaluation.md):
  dead-code, composition, query, portability and documentation gates.
- [Current-state documentation and resource cleanup](current-state-documentation-and-resource-cleanup.md):
  current-authority boundaries, link checks and resource hygiene.
- [SOLID and Secure Workflow Runtime Boundary](solid-secure-runtime-boundary.md):
  one injectable workflow runtime and managed client lifecycle.
- [Typed Request and Work Authorisation](typed-request-work-authorisation.md):
  explicit domain decisions for core request and work access.
- [SOLID and Secure by Design Programme Completion](solid-secure-programme-completion.md):
  architecture fitness, focused configuration and product boundaries.
- [SOLID, readability and maintainability improvement specification](solid-readability-maintainability-ratchets.md):
  executable dependency, complexity, file-size and coverage ratchets.
