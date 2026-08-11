# ADR 0030: Focused use cases and validated security records

## Status

Accepted, 11 August 2026.

## Context

Configuration lifecycle and managed-product transfer behaviour had correct
transaction boundaries, but each public coordinator had accumulated several
different reasons to change. Request audit evidence and workflow-start outbox
payloads also crossed durable security boundaries as general dictionaries.

Adding generic application layers or a dependency-injection framework would
increase indirection without protecting a new boundary. The existing route,
service, repository and infrastructure divisions remain appropriate.

## Decision

Keep the existing public service facades, but compose them from focused use-case
components:

- configuration draft, validation, review and activation;
- product grant preparation, content transfer and scan/promotion; and
- one product transfer context that owns adapters, sessions, audit, cleanup and
  lease recovery.

External network, object-store and scanner activity remains outside database
transactions. The facade preserves current constructors and route contracts.

Represent request audit-chain input, administrative audit hash input and
workflow-start commands as immutable named records. Recursively validate audit
detail values at append and verification boundaries. Permit unknown safe audit
keys for forward-compatible evidence, while bounding key length, collection
size, nesting depth, string length and JSON value types. Parse durable workflow
start commands before dispatch and fail closed on malformed identity fields.
Retain the explicit legacy process identifier only for records already marked
as unpinned by the existing recovery control.

Enforce dependency direction with executable architecture fitness tests. Domain
policy remains framework-free, business HTTP handlers remain straight
delegations, services do not construct SQL expressions, and repositories do not
depend on FastAPI or the Camunda SDK.

## Consequences

- Configuration and product-transfer changes can be reviewed and tested by use
  case without changing the public API.
- Transaction, audit, quarantine and recovery ownership remains explicit.
- Malformed or unexpectedly complex audit evidence is rejected before it is
  hashed or stored.
- Durable workflow-start identity has one serialisation and parsing contract.
- Architecture rules fail in tests if framework or persistence logic crosses
  the protected boundaries.
- There are more small source files, but no new runtime dependency, generic
  layer or service locator.
