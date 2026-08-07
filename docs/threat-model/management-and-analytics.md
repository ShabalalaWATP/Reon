# Management and Analytics Threat Model

## Scope and assets

This model covers management grants, organisation closure, content-free request
facts, stage intervals and scoped statistics APIs and pages. Protected assets are
organisation boundaries, operational measures, staffing state, feedback
confidentiality and the absence of request content or Customer identity from the
reporting path. The expanded scope includes notification response, managed
artefact access, release-cycle, planning, capacity and versioned estimate facts,
plus controlled aggregate CSV and accessible PDF exports.

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
| PDF export renders a broader dataset than the screen | Generate CSV, PDF, chart, table and textual summary from the same authorised, bounded and suppressed tabular rows |
| Dissemination facts reveal product or Customer identity | Record event type, authorised organisation key and timing only; omit product labels, filenames, destinations, request IDs and Customer identifiers |
| Notification measures expose message content | Project event group, safe timing and resolution state only; never ingest notification subject or protected source fields |
| Historical reorganisation rewrites metrics | Attribute facts to the immutable organisation and analytics-definition versions captured at the event; support explicit current and as-of queries |
| A deterministic estimate is presented as a decision | Return inputs, definition version, confidence and freshness, label the value as an estimate and provide no assignment or priority mutation path |
| Planning measures rank an Analyst | Aggregate at authorised team cohort and prohibit person dimensions, league tables and inferred performance scores |
| Repeated export enables small-cohort inference | Apply the same cohort suppression after every filter and comparison, bound dimensions and audit content-free export parameters |
| Export formulas or markup become active content | Generate values through controlled serializers and escape spreadsheet-formula prefixes and PDF text; never render request-derived markup |
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
- Historical configuration-version and retired-unit attribution tests.
- Notification, dissemination, replacement, withdrawal, release-cycle, planning
  and capacity formula oracles using content-free facts.
- Chart, table, textual-summary, CSV and PDF row-parity tests, including zero,
  one, four, five and filtered-comparison cohort boundaries.
- Export formula-prefix, markup, query-bound, authorisation and audit tests.
- Assertions that no dimension or export identifies or ranks an Analyst.
- Deterministic estimate reproducibility, input-version, freshness and advisory
  labelling tests proving there is no automatic decision path.
- Date-range, page-size, query-timeout and performance evidence.
- Keyboard, 200 per cent zoom, chart-table parity and reduced-motion checks.

## Residual risks and gates

Fine-grained operational counts may still be sensitive even without content.
Pilot owners must approve dimensions, cohort size and retention. Production needs
database grants that prevent the analytics identity from reading content tables,
monitored projection lag and tested restore/rebuild procedures.
Aggregate CSV and PDF exports remain disabled until the target-environment owner
accepts their formats, cohort policy, retention and audit requirements.
