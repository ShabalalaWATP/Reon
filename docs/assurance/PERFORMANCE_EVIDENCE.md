# Performance evidence

> Historical MVP evidence. Its workload and thresholds do not establish
> Product Evolution capacity, search, managed-product or recovery performance.

## Environment and thresholds

Recorded on 7 August 2026 against the local production React and FastAPI images,
PostgreSQL 17.9 and Camunda 8.9.14. The programme gate requires a two-minute
warm-up followed by ten minutes at 50 concurrent users, p95 below two seconds,
p99 below four seconds and fewer than one per cent unexpected errors.

The runner uses 50 distinct `admin2` to `admin52` identities, excluding inactive
`admin16`. It discovers only the statistics and team scopes already granted to
each identity, then mixes content-free reads across account, request, queue,
tracking, organisation, statistics, team, board, package and calendar endpoints.
The password is supplied through `LOAD_TEST_PASSWORD` and is never written to an
artefact.

## Baseline formal run

The unscaled local dataset first passed the duration and concurrency gate:

| Measure | Result |
| --- | ---: |
| Requests | 59,479 |
| Concurrent users | 50 |
| Warm-up | 120 seconds |
| Steady state | 600.324 seconds |
| Unexpected errors | 2 transport failures |
| Error rate | 0.003% |
| Mean | 504.52 ms |
| p50 | 235.69 ms |
| p90 | 1,217.74 ms |
| p95 | 1,633.17 ms |
| p99 | 2,568.82 ms |
| Throughput | 99.08 requests/second |

The report is `output/load/formal-baseline-read-load.json`, SHA-256
`974B1D223DF404DD2ED47AEC486CD1BA902ACD71991E6A5562EBE101D6E34759`.

## Agreed-scale fixture

`scripts/seed-performance-data.py` deterministically created a temporary,
non-sensitive OSG Team fixture with:

- 250 active users in the database;
- 5,000 non-recurring calendar events, each producing one occurrence in the
  bounded test window;
- 2,500 work packages with creation activity.

Temporary accounts receive one random, unrecorded password hash and cannot use
the MVP shared password. The fixture self-verifies all counts and fails closed.
Its result is `output/load/performance-fixture.json`, SHA-256
`1C7D3E6186807CFCB940BF900E30936258578B64424C82606ABF9BB933CB7D0B`.

The first short scaled diagnostic found an N+1 package reader and session-row
write contention. The corrected implementation bulk-loads package relations,
bounds package pages to 1–100 records, throttles session activity persistence
without weakening idle validation, and provides a configurable async PostgreSQL
pool. A 1,000-request regression then passed with zero errors, 1,085.47 ms p95
and 1,245.49 ms p99.

## Scaled formal result

Command shape:

```powershell
$env:LOAD_TEST_PASSWORD = '<local-test-password>'
uv run --project apps/api python scripts/run-local-load.py `
  --concurrency 50 --warmup-seconds 120 --duration-seconds 600 `
  --p95-limit-ms 2000 --p99-limit-ms 4000 --error-limit-percent 1 `
  --output output/load/formal-scaled-read-load.json
```

| Measure | Result |
| --- | ---: |
| Requests | 47,154 |
| Concurrent users | 50 |
| Warm-up | 120 seconds |
| Steady state | 600.273 seconds |
| Successful HTTP responses | 47,153 |
| HTTP error responses | 0 |
| Client transport failures | 1 |
| Unexpected error rate | 0.002% |
| Mean | 636.34 ms |
| p50 | 625.98 ms |
| p90 | 857.74 ms |
| p95 | 945.29 ms |
| p99 | 1,114.85 ms |
| Throughput | 78.55 requests/second |

The raw report includes per-path counts and percentiles. It is
`output/load/formal-scaled-read-load.json`, SHA-256
`D504B770D5C1B899C12A70212713515461E209E1A23D4AD55648121A8C9BEAC5`.
The scaled run meets every defined local pilot threshold and exceeds the minimum
2,500 bounded-query request count.

## Data restoration

Before seeding, PostgreSQL was captured as a custom-format dump, SHA-256
`E0B6B68C0E1B3D36FBAFD559ACDF2AA2E90E6416F4CFD5D22FFB777A89AF560E`.
After the run, the API was stopped, that dump was restored with fail-fast clean
replacement, and the API returned healthy. Read-only verification found 71
active demo users, four retained service requests and zero performance package
or calendar records. The temporary performance accounts were therefore not part
of the then-current 72-account MVP organisation. Product Evolution later added
the independent configuration approver `admin73`.

DOD-32 is evidence ready for the local MVP. Production sizing, representative
network latency and an externally accepted capacity model remain deployment
decisions, not hidden claims made by this rehearsal.

## Static efficiency verification, 8 August 2026

A clean Vite production build after route and nested-workspace splitting reduced
the common application chunk from 457.15 kB raw (125.33 kB gzip) to 214.89 kB
raw (67.10 kB gzip). The complete static entry graph, including React and Query
vendor imports, is 300,068 bytes JavaScript plus 95,306 bytes CSS. The build now
fails if those values exceed 325,000 and 110,000 bytes respectively.

The backend notification projection now uses a bounded set of recipient reads
and one checkpoint calculation per selected batch, while unchanged
configuration restoration avoids unit-version and closure write amplification.
These are code-path and behavioural-test results. The current-source target
evidence below now covers PostgreSQL statement counts and worker contention.

## Current-source runtime-scale evidence, 8 August 2026

A clean PostgreSQL 17.9 database migrated to `0019_runtime_scaling`. The updated
deterministic fixture created 250 active users, 2,500 Board packages, 5,000
calendar records and 2,500 rows in each request, draft, staff-work, tracking and
single-request history feed. Synthetic files and product content were not used.

The repository adapters were measured on page one and at a cursor derived from
depth 2,400. Counts remained constant:

| Projection | First-page statements | Deep-page statements | Deep local time |
|---|---:|---:|---:|
| Customer requests | 1 | 1 | 8.89 ms |
| Customer drafts | 1 | 1 | 6.32 ms |
| Staff work | 1 | 1 | 15.83 ms |
| Routing tracking | 4 | 4 | 12.52 ms |
| Administrator users | 1 | 1 | 5.13 ms |
| Board packages | 1 | 1 | 7.20 ms |
| Complete request/history projection | 7 | 7 | 14.33 ms |

`EXPLAIN (ANALYSE, BUFFERS)` returned 51 rows in 0.03 to 3.04 ms for the
representative bounded feed queries. PostgreSQL naturally selected the request,
draft, work, tracking, Board and history indexes. At this small 250-user scale it
correctly preferred a sequential administrator scan; the index-preferred plan
separately proved compatibility with `ix_users_updated_id`. The rehearsal found
and corrected a weaker tracking path by adding
`ix_request_routes_unit_position_request`.

Two overlapping worker instances contended for one named job. Exactly one
callback ran, the second worker reported no work, and the winning generation
recorded success. Storage/scanner tests separately prove that metadata
connections are checked back into the pool before external I/O and slow response
chunks.

The production-built React/FastAPI images then served a 2,500-request,
25-concurrent-user read rehearsal: all 2,500 responses were HTTP 200, throughput
was 90.44 requests/second, p95 was 473.19 ms and p99 was 576.60 ms. This focused
run had no warm-up and does not replace the ten-minute historical formal gate.
Playwright CLI cursor journeys showed 100 visible Customer drafts, work items,
tracked requests and administrator rows after loading another page; Board page
two rendered 25 cards. Measured cursor calls were 31.6 to 51.7 ms.

Generated local evidence:

- fixture SHA-256 `E2E92DF1166E0B0967E9BA5AB4DB7FCBF6564F6D1F719C6F55BD0C6E1B50A691`;
- PostgreSQL/statement/plan evidence SHA-256 `A30CDC1AAAD5C7B3F35E11F95124D28870DF527B753BDE627CEE4D9FFB38ABF6`;
- HTTP load SHA-256 `3EE5C73DA7BBDCB4C024A1649B8CAA081E20CBC6A14786D553EC7132EA328A60`;
- evidence manifest SHA-256 `14A8201CD447BD33CEDFCBEB1BB89A18651DF08DF4134D6F079F3D1EC9A7E0DD`.

The commands are repeatable through `scripts/seed-performance-data.py`,
`scripts/run-runtime-scale-evidence.py`, `scripts/run-local-load.py` and
`scripts/build-runtime-scale-manifest.py`. Results are environment-specific and
do not establish production capacity, autoscaling or an accepted SLO.
