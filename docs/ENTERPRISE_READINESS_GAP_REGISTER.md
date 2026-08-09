# Enterprise readiness gap register

Last reviewed: 9 August 2026

This register prevents local release-candidate capability from being mistaken for
production enterprise readiness. Status values are `IMPLEMENTED`, `EVIDENCE
READY`, `DECISION REQUIRED`, `NOT IMPLEMENTED` and `OUT OF SCOPE`.

| Domain | Current state | Status | Exit evidence or decision |
|---|---|---|---|
| Human-led service workflow | Camunda-coordinated named human decisions and pinned configuration | IMPLEMENTED | Accepted representative-role UAT remains required |
| Routing destination usability | Authorised path breadcrumb, selected-route summary and literal direct-child name/code search are implemented without ranking or global enumeration | IMPLEMENTED, ACCEPTANCE OPEN | Complete representative JIOC, Command and Ops routing UAT on the immutable candidate |
| Organisation configuration | Effective-dated revisions, all-checkpoint preview, canonical approval digest, PostgreSQL snapshot guards, validation, independent approval and guided workspace | IMPLEMENTED | Runtime-role denial and fresh-current-head evidence recorded; Camunda sibling-route, activation race and recovery acceptance remain open |
| Identity and MFA | Synthetic database accounts, Argon2/session controls and shared local fixture password; no OIDC/bootstrap | NOT IMPLEMENTED | Approved OIDC, MFA, claims/group bootstrap, privileged access and account lifecycle |
| Authorisation | Central role, scope, ownership, assignment and action policy | EVIDENCE READY | Full production identity-group and negative-access matrix |
| Segregation of duties | Different-actor configuration approval and independent QC | IMPLEMENTED | Named groups, periodic review and break-glass ownership |
| Data classification | Public-safe synthetic development data only | DECISION REQUIRED | Production classification, handling, residency and privacy assessment |
| Retention and legal hold | Application retention jobs exist for defined MVP records | DECISION REQUIRED | Owner-approved schedule, legal hold and secure disposal procedure |
| Encryption and keys | TLS/deployment responsibility documented; no production key owner | DECISION REQUIRED | KMS/HSM, rotation, certificate and secret ownership |
| Network trust boundaries | Local Compose and private synthetic AWS/GCP/Azure tunnel patterns documented; explicit login proxy trust and isolated ClamAV update egress implemented; Kubernetes target is design-only | NOT IMPLEMENTED | Reviewed IaC, approved production topology, ingress/WAF, egress policy and private monitoring plane with validation evidence |
| PostgreSQL availability | Correct relational source of truth and migrations | NOT IMPLEMENTED | HA topology, failover/failback and production capacity evidence |
| Camunda availability | Camunda 8.9 integration, durable command/outbox, reconciliation and local controlled interruption evidence; client auth only `NONE`/`BASIC` | EVIDENCE READY | Supported licensed target HA cluster, approved authentication and target fault/backup rehearsal |
| Product storage and scanning | Local filesystem quarantine, ClamAV scan, loaded-signature freshness health and authenticated managed downloads implemented; production runtime deliberately absent | NOT IMPLEMENTED | Approved S3/GCS/selected private object adapter, semantic/CDR scanner corpus, owned update path and no-public-access inspection |
| Backup and restore | Local scripts and empty-target rehearsal | EVIDENCE READY | Accepted RPO/RTO, immutable backup, PITR and multi-store restore rehearsal |
| Observability and alerting | Content-free health, readiness and operational metrics | EVIDENCE READY | SIEM integration, alert owners, on-call rota and target-environment tests |
| Service levels | Pilot performance targets documented | DECISION REQUIRED | Accepted SLOs, SLIs, error budgets, load and capacity model |
| Secure development | CI, coverage gates, CodeQL, dependency and secret checks, all-deployed-image Trivy gates and CycloneDX SBOM artefacts | EVIDENCE READY | Accepted immutable release-candidate reports and external penetration test |
| Vulnerability response | Dependabot alerts and automated security updates, scheduled npm/Python/actions/Docker checks, GitHub private vulnerability reporting and a repository policy are enabled | DECISION REQUIRED | Approve severity SLA, accountable ownership, triage coverage and emergency patch process |
| Accessibility | WCAG-oriented components and automated axe coverage | EVIDENCE READY | Manual WCAG 2.2 AA review, 200% zoom and three-browser evidence |
| Audit and non-repudiation | Prior-hash-linked base envelope plus digest-bound configuration approval/activation | EVIDENCE READY | Structured correlation/outcomes, independent audit storage enforcement, retention and SIEM review process |
| Privileged approval evidence | PostgreSQL validates snapshot, lifecycle, actor status, separation and lineage on insert | DECISION REQUIRED | Use a separately controlled evidence writer or identity-bound signature before connected production; a compromised shared runtime credential cannot prove the human actor |
| Change and release management | Candidate release runbook, ADRs, specs, migrations, feature flags and rollback guidance | EVIDENCE READY | Named CAB-equivalent authority, target pipeline and exercised production release/rollback procedure |
| Business continuity | Safe manual escalation, recovery sequence and exercise framework documented | DECISION REQUIRED | Accepted RTO/RPO, manual fallback, invocation authority and multi-store exercise |
| Support and training | Support and configuration runbooks exist | DECISION REQUIRED | Named service desk, training, knowledge ownership and supported hours |
| Vendor and licence assurance | Automated dependency and licence checks | EVIDENCE READY | Camunda and hosting commercial/legal acceptance |
| API lifecycle | Internal versioned API and OpenAPI checks | DECISION REQUIRED | Compatibility, deprecation and external-consumer policy |
| Decommissioning | Not required for local MVP | OUT OF SCOPE | Production data export, deletion and service-exit plan before launch |

## Production blockers

The product must not be described as enterprise-ready or used with real service
content until production identity, hosting, named ownership, classification,
penetration testing, accepted RPO/RTO, operational monitoring and the applicable
Product Evolution Definition of Done gates are accepted.

Setting `ENVIRONMENT=prod` does not remove these blockers. In particular, the
repository has no application OIDC/bootstrap, production object-storage runtime,
Kubernetes/application Helm manifests, cloud infrastructure as code or validated
production topology. The built-in managed-product runtime is rejected in
production, and local unauthenticated Camunda must never be exposed.
