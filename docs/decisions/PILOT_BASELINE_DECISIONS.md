# Current evaluation baseline decisions

## Purpose

This register fixes the current local synthetic-evaluation baseline and makes the
remaining human ownership decision explicit. It is not production approval.
Every row has a decision, date and rationale. DOD-00 remains open until a named
person accepts each accountable role and signs this register.

Recorded on 7 August 2026. Last reviewed against the current synthetic candidate
on 18 August 2026.

## Current local evaluation baseline

| ID | Decision | Rationale | Accountable role | Named owner | State |
| --- | --- | --- | --- | --- | --- |
| BL-01 | The pilot contains synthetic, public-safe information only. Real operational, personal, sensitive or classified content is prohibited | Allows representative workflow testing without creating an information-handling system by implication | Product and security owners | PENDING NOMINATION | Implemented, acceptance required |
| BL-02 | The evaluation uses the 108 documented Scottish-football identities and local-only `admin` passwords. The credentials must never leave local/test | Meets the requested test-account model while clearly excluding it from production identity | Product and security owners | PENDING NOMINATION | Implemented, acceptance required |
| BL-03 | PostgreSQL 17.10 is the system of record and Camunda 8.9.14 coordinates human tasks. Camunda does not choose routes or approve work | Keeps business state durable and human routing explicit | Technical and workflow owners | PENDING NOMINATION | Implemented, acceptance required |
| BL-04 | The initial primary route is JIOC, DIGOC, NCGI-A Ops and OSG Team. Every configured sibling route remains selectable and separately staffed | Proves the organisation model can expand without embedding an OSG Team fallback | Product owner | PENDING NOMINATION | Implemented, acceptance required |
| BL-05 | Products are quarantined PDF, DOCX, PPTX, PNG or JPEG files released through authenticated downloads, or normalised allow-listed HTTPS links. Files require structural validation and malware scanning, and the backend never fetches supplied links | Provides the required dissemination choices while controlling upload, active-content and server-side request risks | Product and security owners | PENDING NOMINATION | Implemented, acceptance required |
| BL-06 | Customer submission fields, feedback rating and feedback comments are mandatory. Drafts may remain incomplete until submission | Protects submitted-data quality while preserving private work in progress | Product owner | PENDING NOMINATION | Implemented, acceptance required |
| BL-07 | JIOC, command and Ops groups route and track work but do not approve the return path. A Team Analyst submits to the Team Manager; a QC User or QC Manager reviews, and a different QC Manager disseminates | Matches the agreed human-led operating model and separation of duties | Product and workflow owners | PENDING NOMINATION | Implemented, acceptance required |
| BL-08 | Statistics contain content-free operational facts and are limited to server-authorised scope: explicit management reporting grants or the bounded Platform Administrator platform scope | Supports workload oversight without exposing request or product content | Product and security owners | PENDING NOMINATION | Implemented, acceptance required |
| BL-09 | Supported pilot browsers are the installed current stable Chrome, Edge and Firefox at desktop and 390-pixel narrow width | Gives the pilot a concrete compatibility boundary | Product owner | PENDING NOMINATION | Technically proved, acceptance required |
| BL-10 | Ordinary, statistics, calendar and board reads target p95 below 2 seconds, p99 below 4 seconds and unexpected errors below 1 per cent at 50 concurrent users | Establishes measurable performance exit criteria | Product and operational owners | PENDING NOMINATION | Technically proved, acceptance required |
| BL-11 | Supported hours are Monday to Friday, 08:00 to 18:00 Europe/London excluding public holidays; incident severities and response targets follow the support runbook | Makes service expectations testable before nomination of named responders | Operational owner | PENDING NOMINATION | Defined, acceptance required |
| BL-12 | Retention policy v2 deletes or anonymises eligible short-lived and expired records in bounded, legal-hold-aware batches under explicit disposal authority. Completed requests and products are reported but fail closed on apply until coordinated object disposal exists | Removes expired data without silently breaking accountable history or orphaning stored product content | Product, security and operational owners | PENDING NOMINATION | Implemented with request and product disposal adapter still gated |
| BL-13 | The local Compose topology is not a production deployment. OIDC, hosting region, private networking, certificates, secrets management and production Camunda licensing remain separate production decisions | Prevents technical MVP evidence being mistaken for authority to deploy | Product, security and operational owners | PENDING NOMINATION | Explicitly deferred |
| BL-14 | The reviewed baseline must use an approved remote with recorded visibility, or a signed local-only exception | Preserves change history and review evidence without assuming authority to publish | Repository owner | ShabalalaWATP | Public remote explicitly selected and implemented |

## Baseline measures

| Measure | Pilot target | Current evidence |
| --- | ---: | ---: |
| Submitted requests with every required field | 100% | UI and API enforcement proved |
| Requests with visible immutable status history | 100% | Customer and tracker journeys proved |
| Released products available through authenticated dashboard download or redirect | 100% | Chrome, Edge and Firefox journeys proved |
| Completed requests with requested feedback opportunity | 100% | Chrome, Edge and Firefox journeys proved |
| Cross-scope request-content disclosure | 0 | Server-side abuse matrix passed |
| Unexpected workflow branch fallback | 0 | OSG Team and alternative routes proved |
| Ordinary operation p95 | Less than 2 seconds | 945.29 ms at formal scale |
| Unexpected error rate at formal scale | Less than 1% | 0.002% |
| Recovery from controlled database or Camunda interruption | Less than 15 minutes without loss or duplication | Local rehearsals passed |

## Acceptance

The following people must be named before DOD-00 can be accepted.

| Role | Name | Decision date | Signature or approved record |
| --- | --- | --- | --- |
| Product owner |  |  |  |
| Security owner |  |  |  |
| Operational owner |  |  |  |
| Technical owner |  |  |  |
| Workflow owner |  |  |  |
| Repository owner |  |  |  |
