# ADR 0037: Executable SOLID and readability ratchets

## Status

Accepted

## Context

Mist Service has strong tests and clear external adapter boundaries, but the
August 2026 maintainability review found that the existing architecture fitness
tests did not prevent application services from importing concrete persistence,
repositories from importing service records, broad protocols, package cycles or
dense frontend orchestration.

Failing every current violation at once would stop unrelated delivery and invite
the checks to be disabled. Allowing the current state without measurement would
permit the debt to grow. A score such as "8.5" is useful for communicating the
target but is not deterministic enough to serve as a quality gate.

## Decision

Adopt executable, monotonically shrinking architecture ratchets:

1. Parse Python imports and class definitions with the standard AST rather than
   relying on text searches.
2. Record current service-to-infrastructure, service-to-composition,
   router-to-persistence and repository-to-service coupling as per-module
   counts. New modules and increased counts fail.
3. Detect internal dependency cycles as deterministic strongly connected
   components.
4. Limit application protocols to 12 declared methods and record any current
   wider interface with a non-increasing ceiling.
5. Retain the 350-line hard limit and add a 330-line refactoring target. Current
   exceptions receive non-increasing ceilings.
6. Keep raw browser requests and API route construction inside API adapters.
7. Require protected server-state keys to come from the central context-aware
   factory, with literal legacy usages recorded until removed.
8. Enforce frontend complexity 12 and nesting depth four for new code. Existing
   orchestration modules receive exact measured file-level maxima. A dedicated
   gate fails both increases and stale baselines after responsibility is
   extracted.
9. Treat a baseline change as valid only when the corresponding implementation
   removes debt. Updating measurements alone is not remediation.

## Consequences

- Architecture drift becomes a test failure with an actionable module name.
- Existing delivery can continue while every architectural change is forced to
  move the measured baseline in one direction.
- Coarse per-module counts can theoretically exchange one import for another.
  Review must therefore inspect baseline changes, and the target state remains
  an empty map rather than a permanently accepted count.
- File-level complexity ceilings are less precise than per-function baselines,
  but are supported directly by ESLint and make new high-complexity modules fail.
- The tests add a small analysis cost to the backend suite and no runtime cost to
  the service.

## Alternatives considered

- **Fail every current violation immediately:** rejected because it would make
  the main quality gate unusable during staged remediation.
- **Document principles without executable checks:** rejected because prior
  review showed that conventions alone did not prevent dependency drift.
- **Introduce a dependency-injection framework:** rejected because explicit
  composition and small protocols solve the observed boundary problem without
  a new runtime abstraction.
- **Use a subjective score as the gate:** rejected because the score cannot
  identify a concrete regression or be reproduced in CI.
- **Format the repository before refactoring:** deferred because a broad
  mechanical diff would obscure the behavioural and architectural changes.
