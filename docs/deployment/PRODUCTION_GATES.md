# Production deployment gates

Status: blocking acceptance checklist

Passing local tests is necessary but not sufficient. ISTARI must not contain real
service content or be called enterprise-ready until every applicable row below
has dated evidence, an accountable owner and explicit acceptance.

| Gate | Required evidence | Current state |
|---|---|---|
| Identity | OIDC/MFA integration, first-admin enrolment, group mapping, logout, revocation, joiner/mover/leaver and break-glass tests | Not implemented |
| Camunda security | Supported/licensed topology, HTTPS, client authentication, authorisation, tenant/group controls and private ingress tests | Local topology is unprotected |
| Product runtime | Private cloud object adapter, durable upload grants, approved scanner/CDR, quarantine/release policy and replica-crossing tests | Not implemented |
| Platform code | Reviewed IaC, Kubernetes/application deployment assets, policy-as-code and drift detection | Not implemented |
| Database | Managed PostgreSQL bootstrap, `ssl=verify-full`, role separation, capacity budget, PITR and failover/failback evidence | Target only |
| Edge security | Approved DNS/TLS, WAF/login rate limits, trusted-proxy handling, HSTS, host tests and private API | Shared application limiter and explicit proxy trust implemented; managed edge, TLS and HSTS target not implemented |
| Secrets and keys | Workload identity, secret-manager injection, certificate rotation, audit-key keyring/rotation and access tests | Not implemented |
| Supply chain | Locked dependencies, SBOMs, all-image/IaC scans, image signatures, provenance and admission verification | Locked dependency audits, all-five-image scans and CycloneDX SBOMs implemented in CI; IaC scans, signing, provenance and admission remain open |
| Availability | Replica, lease-contention, disruption, zone-failure and dependency-recovery evidence against accepted SLOs | Not accepted |
| Recovery | Joined PostgreSQL, Camunda and object-store backup/restore exercise against accepted RPO/RTO | Local database evidence only |
| Observability | Content-free logs/metrics/traces, dashboards, alerts, SIEM routing, on-call rota and alert exercises | Foundations only |
| Security assurance | Updated threat model, abuse-case tests, external penetration test and no unaccepted high/critical finding | Current local automated evidence ready; external penetration test and owner acceptance open |
| Privacy and data | Classification, residency, retention, legal hold, disposal, DPIA where required and supplier approval | Decision required |
| Accessibility and UAT | Manual WCAG 2.2 AA evidence and named representative-role journeys | Acceptance open |
| Operations | Release, incident, support, continuity, access-review, change and decommissioning owners | Decision required |

## Gate procedure

1. Assign an accountable owner and reviewer to each row.
2. Define the exact target environment and immutable candidate. Evidence from a
   developer laptop does not prove a managed cloud control.
3. Link automated reports, manual exercises, decisions and residual risks. Do
   not paste secrets, real request content or restricted topology into this
   public-safe repository.
4. Require security-owner acceptance for residual risk and business-owner
   acceptance for service/data risk.
5. Re-run affected gates after any identity, network, data, workflow, storage,
   scanner, dependency, platform or recovery change.
6. Record the release decision in the acceptance record and gap register.

## Minimum go/no-go rule

The result is **no-go** when a required gate is missing, evidence belongs to a
different candidate/environment, an unresolved high or critical security issue
exists, restore has not been exercised, or accountable acceptance is absent.
Feature flags and `ENVIRONMENT=prod` do not waive these gates.

The detailed current backlog remains in the
[enterprise readiness gap register](../ENTERPRISE_READINESS_GAP_REGISTER.md).
