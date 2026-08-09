# Enterprise documentation index

Status: release-candidate index, not enterprise acceptance
Last reviewed: 9 August 2026

This index identifies the authoritative evidence and the missing accountable
decisions. A document marked **Gap** must not be inferred from working code.

| Enterprise area | Current authority | State |
|---|---|---|
| Product scope and complex stories | [Product evolution](specs/operational-product-evolution.md), [configuration usability](specs/configuration-administration-usability.md), [operator orientation](specs/operator-orientation-and-service-timing.md), [runtime hardening](specs/runtime-scaling-and-worker-hardening.md) | Implemented specifications, acceptance open |
| Architecture and SOLID boundaries | [System architecture](architecture/SYSTEM_ARCHITECTURE.md), [foundations](architecture/FOUNDATIONS.md), [ADRs](adr/) | Current implementation and portable-evaluation boundary documented; target validation open |
| Organisation and users | [Organisation and routing](architecture/ORGANISATION_AND_ROUTING.md) | Synthetic MVP documented; [mock users](reference/MOCK_USERS.md) is a locator only |
| Routing destination usability | HRU-01 to HRU-08 in the [configuration usability specification](specs/configuration-administration-usability.md) and [configuration/routing evidence](assurance/CONFIGURATION_AND_ROUTING_EVIDENCE.md) | Direct-child selection, authorised route breadcrumb and literal name/code search implemented; representative acceptance open |
| Roles and segregation of duties | [Role-permission matrix](reference/ROLE_PERMISSION_MATRIX.md) | Documented, production group mapping open |
| Requirements traceability | [Specification traceability](assurance/SPECIFICATION_TRACEABILITY.md) | Release-candidate mapping documented |
| Threat modelling and security remediation | [Threat models](threat-model/), [August security specification](specs/security-remediation-2026-08.md), [shared-throttle/runtime ADR](adr/0021-shared-login-throttling-and-hardened-runtime-images.md) | Updated, owner acceptance open |
| Audit design | [Audit event catalogue](security/AUDIT_EVENT_CATALOGUE.md) | Partial enterprise metadata |
| Secure operations and incidents | [Security policy](../SECURITY.md), [support and incident runbook](operations/SUPPORT_AND_INCIDENT_RUNBOOK.md), [configuration runbook](operations/CONFIGURATION_AND_ROUTING_RUNBOOK.md) | Private-reporting route and local procedure documented; named owners open |
| Backup, recovery and continuity | [Migration and restore evidence](assurance/MIGRATION_AND_RESTORE_EVIDENCE.md), [recovery evidence](assurance/RECOVERY_EVIDENCE.md), [continuity plan](operations/BUSINESS_CONTINUITY_AND_DISASTER_RECOVERY.md) | Framework and local evidence, production plan open |
| Verification and acceptance | [Product Evolution DoD](assurance/PRODUCT_EVOLUTION_DEFINITION_OF_DONE_MATRIX.md), [configuration evidence](assurance/CONFIGURATION_AND_ROUTING_EVIDENCE.md) and [acceptance record](assurance/PRODUCT_EVOLUTION_ACCEPTANCE_RECORD.md) | Automated evidence in progress, signatures open |
| Running application visuals | [Current screenshots and browser evidence](assurance/BROWSER_AND_WORKFLOW_EVIDENCE.md#current-application-screenshots) | Four synthetic representative surfaces retained; visual and representative acceptance remain open |
| Enterprise readiness | [Gap register](ENTERPRISE_READINESS_GAP_REGISTER.md) | Explicit blockers maintained |
| Deployment and network trust boundary | [Deployment guides](deployment/README.md), [system architecture](architecture/SYSTEM_ARCHITECTURE.md) | Local/synthetic procedures and unimplemented target documented; IaC and validated production topology remain **Gaps** |
| Data classification, privacy and residency | Synthetic-only boundary | **Gap:** classification, retention approval and DPIA where applicable |
| Service levels and capacity | [Current and historical local performance evidence](assurance/PERFORMANCE_EVIDENCE.md) | **Gap:** accepted SLIs, SLOs, error budgets and sizing model |
| Observability and alert ownership | Content-free health foundations | **Gap:** target dashboards, SIEM, alert catalogue and on-call ownership |
| Release and change management | [Release runbook](deployment/RELEASE_RUNBOOK.md), specs, ADRs, migrations and CI | Candidate procedure documented; production authority and connected execution remain **Gaps** |
| Access lifecycle | Account and membership application controls | **Gap:** joiner/mover/leaver, PAM, access review and break-glass procedure |
| Support and training | Local runbooks | **Gap:** support model, service hours, training and knowledge ownership |
| Data dictionary and API lifecycle | OpenAPI and schema source | **Gap:** owned business glossary, compatibility and deprecation policy |
| Supplier, licence and exit | Automated dependency/licence checks | **Gap:** contracts, support, escrow and decommissioning plan |

The gap register is the status authority. This index is navigation, not a claim
that every enterprise document has been approved.

## Architecture and deployment guides

| Subject | Authority |
|---|---|
| Documentation navigation | [Documentation map](README.md) |
| Context, components, authorities, data flow, failure and scaling | [System architecture](architecture/SYSTEM_ARCHITECTURE.md) |
| Local Windows, macOS and Linux Compose | [Local Docker](deployment/LOCAL_DOCKER.md) |
| Local API/web source development | [Local source development](deployment/LOCAL_SOURCE_DEVELOPMENT.md) |
| Private synthetic cloud-host evaluation | [AWS sandbox](deployment/AWS_SANDBOX.md), [GCP sandbox](deployment/GCP_SANDBOX.md), [Azure sandbox](deployment/AZURE_SANDBOX.md) |
| Configuration variables and production invariants | [Configuration reference](deployment/CONFIGURATION_REFERENCE.md) |
| Unimplemented connected target | [Kubernetes target](deployment/KUBERNETES_TARGET.md) |
| Candidate qualification and launch blockers | [Release runbook](deployment/RELEASE_RUNBOOK.md), [production gates](deployment/PRODUCTION_GATES.md) |

AWS, GCP and Azure host guides reuse loopback-only Compose behind a protected
management tunnel. They are not production architectures. Kubernetes is a target
design only: the repository has no IaC, application chart, OIDC/bootstrap,
production Camunda auth adapter, S3/GCS product runtime or validated topology.

## Documentation ownership and duplication control

Each durable fact has one authority. Other documents should link to it and add
only the context required for their own purpose.

| Information | Authority | Other documents should |
| --- | --- | --- |
| Product requirements and acceptance criteria | Applicable file in `docs/specs/` | Link to requirement IDs |
| Current delivery status and next work | `docs/MASTER_IMPLEMENTATION_PLAN.md` | Avoid copying task lists |
| Chronological engineering record | `docs/DEVELOPMENT_STORY.md` | Record only new dated events |
| Organisation, routes and complete mock-user directory | `docs/architecture/ORGANISATION_AND_ROUTING.md` | Link to the relevant heading |
| Enterprise blockers | `docs/ENTERPRISE_READINESS_GAP_REGISTER.md` | Link to the gap row rather than restating it |
| Architecture decisions | The numbered ADR | Link to the ADR and do not rewrite its decision |
| Security risks and controls | Applicable file in `docs/threat-model/` | Link from specs and assurance records |
| Operational procedure | Applicable file in `docs/operations/`; installation/release procedure in `docs/deployment/` | Keep evidence and policy out of the procedure |
| Test or rehearsal result | Dated file in `docs/assurance/` | Treat it as immutable evidence and supersede by link |

README content remains an entry point, not a second specification. Historical
assurance records may retain old measurements, but must be labelled historical
and link to the current status authority.

## Assurance record lifecycle

Assurance files are not interchangeable status documents. They are retained when
they preserve a dated result, acceptance boundary or reproducible evidence that
would otherwise be lost. Executed task plans and small evidence indexes are
merged into their durable authority rather than retained as parallel documents.

| Record group | Authorities | Retention reason |
| --- | --- | --- |
| Current release-candidate status | [Master plan](MASTER_IMPLEMENTATION_PLAN.md), [gap register](ENTERPRISE_READINESS_GAP_REGISTER.md), [Product Evolution DoD](assurance/PRODUCT_EVOLUTION_DEFINITION_OF_DONE_MATRIX.md), [Product Evolution acceptance](assurance/PRODUCT_EVOLUTION_ACCEPTANCE_RECORD.md) | Current work, open gates and named acceptance remain easy to distinguish |
| Requirement and configuration traceability | [Specification traceability](assurance/SPECIFICATION_TRACEABILITY.md), [configuration and routing](assurance/CONFIGURATION_AND_ROUTING_EVIDENCE.md) | Maps implemented controls to accepted requirement identifiers |
| Runtime, security and recovery evidence | [Performance](assurance/PERFORMANCE_EVIDENCE.md), [migration and restore](assurance/MIGRATION_AND_RESTORE_EVIDENCE.md), [recovery](assurance/RECOVERY_EVIDENCE.md), [security matrix](assurance/SECURITY_MATRIX_EVIDENCE.md), [security scans](assurance/SECURITY_SCAN_EVIDENCE.md), [log minimisation](assurance/LOG_DATA_MINIMISATION_EVIDENCE.md) | Preserves dated commands, measurements, hashes and limitations |
| Browser and accessibility evidence | [Browser, screenshots and workflow](assurance/BROWSER_AND_WORKFLOW_EVIDENCE.md), [accessibility](assurance/ACCESSIBILITY_EVIDENCE.md) | Separates current visual orientation from dated browser and accessibility checks |
| Historical MVP closure | [Definition of Done](assurance/DEFINITION_OF_DONE_MATRIX.md), [expansion evidence](assurance/EXPANSION_EVIDENCE.md), [final completion audit](assurance/FINAL_COMPLETION_AUDIT.md), [pilot acceptance](assurance/PILOT_ACCEPTANCE_RECORD.md), [source-control baseline](assurance/SOURCE_CONTROL_BASELINE.md) | Retains the accepted technical baseline without presenting it as current Product Evolution acceptance |

Markdown documentation is deliberately exempt from the 350-line hand-written
source limit. Complex specifications, directories, threat models and evidence
may exceed 400 lines when that improves traceability. They should instead use a
clear heading hierarchy and, when necessary, a contents section. Source-code,
configuration and executable-script limits remain unchanged.
