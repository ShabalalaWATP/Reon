# Management and Analytics Threat Model

## Scope and assets

This model covers management grants, organisation closure, content-free request
facts, stage intervals and scoped statistics APIs and pages. Protected assets are
organisation boundaries, operational measures, staffing state, feedback
confidentiality and the absence of request content or Customer identity from the
reporting path.

## Trust boundaries

```text
Manager browser -> React statistics workspace -> FastAPI policy and query service
                                            -> PostgreSQL grants and closure
                                            -> content-free facts and intervals

Request narrative, product content and feedback comments do not cross into the
analytics repository.
```

## Threats and controls

| Threat | Control |
| --- | --- |
| Client supplies a sibling or ancestor unit ID | Load the active grant and derive allowable units from closure inside the final repository query |
| Broad role grants unintended access | Keep action-specific management grants independent of role labels and membership |
| Expired or revoked authority remains cached | Validate grant dates and version on every request; use short content-free client caching only |
| Organisation cycle expands scope | Enforce cycle-free parent mutations and closure-table constraints transactionally |
| Administrator reporting exposes request content | Serve aggregates from content-free facts only and retain request-repository denial |
| Feedback identifies a small group | Suppress rating aggregates and child comparisons below a cohort of five |
| Timing or filters reveal a single Customer | Bound dimensions, avoid free-text grouping and apply cohort suppression to sensitive measures |
| Projection duplicates inflate metrics | Use unique event keys, projection versions and idempotent upserts; reconcile against source counts |
| Stale projection misleads a manager | Return freshness and degraded state; alert on lag instead of presenting it as current |
| Large ranges cause denial of service | Limit date range, dimensions and page size; use statement timeout and indexed closure joins |
| CSV or table export bypasses scope | Use the same scoped query and suppression service; no separate unrestricted export path |
| Analytics logs leak identifiers | Log grant, unit and metric keys only; never log request IDs, Customer IDs or comments |
| Grant mutation is repudiated | Require reason, expected version and append-only audit with actor and before/after metadata |

## Required evidence

- Positive tests for exact-unit and descendant grants at every hierarchy level.
- Negative tests for ancestor, sibling, unrelated, expired, revoked and stale
  grants, including direct identifier manipulation.
- A fixed-fixture aggregate oracle for counts, durations and date boundaries.
- Assertions that analytics schemas, SQL results, logs and audit contain no
  narrative, product, Customer identity or feedback comment.
- Cohort suppression tests at zero, one, four, five and combined child totals.
- Projection duplicate, out-of-order, rebuild and lag tests.
- Date-range, page-size, query-timeout and performance evidence.
- Keyboard, 200 per cent zoom, chart-table parity and reduced-motion checks.

## Residual risks and gates

Fine-grained operational counts may still be sensitive even without content.
Pilot owners must approve dimensions, cohort size and retention. Production needs
database grants that prevent the analytics identity from reading content tables,
monitored projection lag and tested restore/rebuild procedures.
