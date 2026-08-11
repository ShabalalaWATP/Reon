# SOLID and Secure by Design review

## Scope and status

This implementation review covers the 11 August 2026 programme changes. It is a
source, automated-tool and local-runtime review. It is not an external
penetration test, production accreditation or named security-owner acceptance.

Three separate review lenses were applied after implementation. Executable
fitness rules and security tools provide independent repeatable checks, while
the conclusions below remain an internal engineering assessment.

## Architecture and SOLID review

### Result

Pass for the implemented boundary, with no new generic layer or dependency-
injection framework.

| Principle | Evidence and conclusion |
|---|---|
| Single responsibility | Configuration draft, validation, review and activation are separate. Product grant, byte transfer and scan/promotion are separate. Compatibility facades contain delegation only. |
| Open and closed boundaries | API and worker composition depend on `WorkflowEngine`; Camunda SDK construction can change inside the managed runtime adapter. Product storage, scanner and audit remain ports. |
| Substitutability | Existing fake workflow and product adapters pass the same behaviour suites as the composed runtime path. Public service constructors and methods remain compatible. |
| Interface segregation | Workflow composition receives the narrow engine port. Request/work policies receive immutable domain records. Transfer coordinators receive one explicit context instead of unrelated infrastructure globals. |
| Dependency inversion | Domain policies import no FastAPI, SQLAlchemy or Camunda modules. Composition roots select concrete adapters. |

The architecture fitness suite checks framework-free policy modules, SQL-free
and branch-free business route handlers, repository-only SQL expression
construction and framework-free repositories. The suite passed four rules.

### Deliberate limits

Repository and projection adapters still use SQLAlchemy because persistence is
their responsibility. Facades remain because changing every route and test
caller would add migration risk without improving the protected boundary.

## Code-quality review

### Result

Pass.

- Ruff formatting and linting passed the complete Python tree.
- MyPy passed 308 source files with strict untyped-definition and generic rules.
- Vulture and Knip found no reportable dead code.
- The 350-line source limit passed after shared authorisation test builders were
  separated by responsibility.
- Root documentation, terminology, OpenAPI, operations, licence and Dependabot
  contracts passed.
- The production web build and bundle budget passed.

The complete frontend suite initially recorded changing timing failures while
many UI suites competed for resources. Each affected suite passed directly. The
complete coverage suite then passed with four bounded workers at 99.50 per cent
line and 95.00 per cent branch coverage. This is retained as a local runner
capacity observation, not a product failure.

The authoritative backend suite passed 1,018 tests at 98.87 per cent statement
and 95.16 per cent branch coverage. Neither independent threshold was rounded
up, excluded or lowered.

## Secure by Design review

### Result

Pass for the local MVP engineering boundary. Connected or production use
remains blocked by the existing production gates.

| UK government Secure by Design theme | Implemented control |
|---|---|
| Understand the context | Current architecture, authorities, trust boundaries, threat models and explicit production exclusions remain documented. |
| Make security a business requirement | Non-disclosing object access, exact route/team scope, mandatory human decisions, audit integrity and recovery are acceptance criteria rather than UI conventions. |
| Secure defaults | Malformed workflow commands and audit evidence fail closed. Production refuses local product storage. API documentation and permissive transport settings are environment bounded. |
| Least privilege | PostgreSQL roles are separated. Request/work policies repeat object and action checks after scoped repository reads. Camunda receives content-free identifiers and candidate groups only. |
| Defence in depth | Session, CSRF, role, scope, object, assignment, version, workflow-state and repository-query controls are independent. Tamper-evident chains authenticate request and administrative changes. |
| Minimise attack surface | Entry points cannot import the Camunda SDK, routes cannot build SQL, business services cannot construct SQL expressions and no new runtime dependency was added. |
| Protect data | Audit detail size and type are bounded, logs remain content-free, product bytes stay quarantined until scan, and external links remain allowlisted. |
| Resilience and recovery | Durable outboxes, fenced leases, idempotent start identity and controlled readiness were exercised under live PostgreSQL and Camunda interruption. |
| Assure continuously | CI includes Ruff, MyPy, Bandit, tests, CodeQL, dependency audits, secret scanning, image scanning, SBOMs and a bounded Camunda smoke. |

Bandit scanned 45,044 lines with zero low, medium or high finding. Locked Python
and Node dependency audits reported no known vulnerability. The source-owned
secret, dependency and workflow contracts passed through the root static gate.

## Recovery review

Forty-one focused restore, workflow recovery, cancellation, dispatch and
operational-snapshot tests passed. The retained local stack then showed:

- Camunda stopped: readiness returned controlled HTTP 503 with database,
  configuration and maintenance still healthy and workflow unavailable;
- Camunda restarted: full readiness returned in 42.48 seconds;
- PostgreSQL stopped: readiness returned controlled HTTP 503 with database,
  configuration and maintenance unavailable while workflow remained healthy;
- PostgreSQL restarted: full readiness returned in 11.80 seconds; and
- no volumes, requests or user data were removed.

Both results are comfortably inside the local 15-minute dependency recovery
target. They do not prove a coordinated production backup/restore or disaster-
recovery objective.

The rebuilt API and worker images then started against the retained services.
`/health` returned 200, `/ready` returned every check as `ok`, unauthenticated
`/api/v1/auth/me` returned the intended generic 401, and a synthetic demo login
returned 200.

## Residual risks and required external evidence

- Replace MVP authentication with the approved OIDC and MFA design.
- Configure authenticated TLS Camunda access for the connected target.
- Implement approved cloud storage, scanning, key management and lifecycle
  controls before product content is connected.
- Complete deployment IaC, joined multi-store recovery and target-environment
  monitoring.
- Obtain named security-owner acceptance, an independent penetration test where
  required, accessibility acceptance and representative operational acceptance.
