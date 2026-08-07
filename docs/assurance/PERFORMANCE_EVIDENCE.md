# Performance evidence

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
or calendar records. The temporary performance accounts are therefore not part
of the product's documented 72-account organisation.

DOD-32 is evidence ready for the local MVP. Production sizing, representative
network latency and an externally accepted capacity model remain deployment
decisions, not hidden claims made by this rehearsal.
