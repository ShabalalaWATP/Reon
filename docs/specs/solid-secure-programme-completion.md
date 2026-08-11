# SOLID and Secure by Design Programme Completion

## Status

Implementation milestone, 11 August 2026.

## Objective

Complete every remaining engineering item in the SOLID and Secure by Design
improvement programme without changing the representative workflow, permissions
or user interface. This specification follows the managed Camunda runtime and
typed request/work authorisation milestones.

## Scope

### Architecture fitness

- Domain policy modules must not import FastAPI, SQLAlchemy or Camunda.
- Business HTTP endpoints must remain straight delegation boundaries. They must
  not contain branching workflow logic or direct SQLAlchemy access.
- Application services must not build SQL expressions. Persistence query
  construction remains in repositories or named persistence/projection adapters.
- Composition roots and infrastructure adapters may import concrete frameworks.

### Configuration lifecycle separation

- Draft creation and replacement form one use-case component.
- Validation and submission form one use-case component.
- Independent review remains separate.
- Activation and materialisation form one use-case component.
- A small compatibility facade retains the existing public service contract and
  shares one repository, settings, publisher and clock boundary.
- Audit and event publication remain mandatory and transaction-owned.

### Managed-product transfer separation

- Upload-grant preparation, byte transfer and scan/promotion are separate
  coordinators.
- One transfer context owns the session factory, runtime adapters, audit port,
  lease release and quarantine cleanup.
- External I/O remains outside database transactions.
- A small compatibility facade retains existing route and test contracts.

### Validated security records

- Request audit details use a bounded, recursively validated JSON value type.
- Audit-chain verification consumes a named immutable event record instead of
  indexing arbitrary dictionaries.
- Workflow-start commands use a validated immutable type for serialisation and
  parsing at the PostgreSQL-to-Camunda boundary.
- Audit detail keys that are not yet known remain permitted for forward
  compatibility, but depth, size, key shape and JSON value types are bounded.
- No sensitive values are added to logs or metrics.

### Assurance

- Complete architecture, maintainability and defensive security reviews against
  the changed boundary.
- Pass independent line and branch coverage gates without exclusions or lower
  thresholds.
- Pass repository quality, dead-code, documentation, licence, OpenAPI, type and
  lint gates.
- Exercise current PostgreSQL restore verification and Camunda interruption or
  recovery controls using the repository-owned safe local procedures.
- Rebuild the local API and worker and prove health, readiness and authentication
  boundary behaviour.

## Compatibility requirements

- No BPMN, database schema or public API contract change.
- Existing service constructors and public methods remain usable.
- Existing audit hashes remain reproducible from stored events.
- Unknown or malformed workflow-start payloads fail closed.
- No Platform Administrator gains request-content access.

## Acceptance evidence

1. Architecture fitness tests fail for a domain framework import, SQL in a route
   or service, or branching business endpoint.
2. Configuration and product transfer facades delegate to separately testable
   use-case components.
3. Audit validation rejects unsupported values, unsafe keys, excessive depth and
   excessive collection size while accepting existing event details.
4. Workflow-start serialisation and parsing reject missing, invalid or
   inconsistent identity fields.
5. Existing behaviour tests and public contracts pass unchanged.
6. Full coverage and repository gates pass.
7. Recovery evidence records the exact commands, time and result without
   overstating local evidence as production acceptance.

## Out of scope

- Human accessibility or operational-owner acceptance that requires named
  external participants.
- Production deployment, production DAST or destructive production recovery.
- Replacing SQLAlchemy, Camunda or PostgreSQL.
- Adding dependency-injection frameworks or generic service registries.
