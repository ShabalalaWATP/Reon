# Security scan evidence

## SOLID and Secure by Design programme, 11 August 2026

The current programme candidate passed Ruff formatting and lint, MyPy across
308 source files, Vulture and Knip dead-code checks, and the 350-line source
limit. Bandit scanned 45,044 lines of application and migration code with zero
low, medium or high finding. Strict audit of the lock-derived Python dependency
set and the Node high-severity dependency audit both reported no known
vulnerability.

The authoritative backend suite passed 1,018 tests at 98.87 per cent statement
and 95.16 per cent branch coverage. The full frontend suite passed with bounded
local worker concurrency at 99.50 per cent line and 95.00 per cent branch
coverage. Root secret-scan, dependency-policy, Dependabot, OpenAPI, operations,
documentation, licence and production-build contracts passed. Hosted CodeQL,
container scanning and current-source secret scanning remain CI controls and
are not restated as newly executed local scans.

The detailed architecture, code-quality, UK government Secure by Design and
residual-risk assessment is in
[SOLID and Secure by Design review](SOLID_SECURE_BY_DESIGN_REVIEW.md).

## Unified workspace source verification, 10 August 2026

The complete current source passed Ruff formatting and lint across 485 Python
files, MyPy across 290 source files, Bandit across 43,405 lines with zero low,
medium or high finding, and the repository's Knip and Vulture dead-code gates.
Strict `pip-audit` of the lock-derived third-party dependency export and
`pnpm audit --audit-level=high` both reported no known vulnerability. The
936-test backend suite passed at 98.85 per cent line and 95.03 per cent branch
coverage; the 327-test frontend suite passed at 99.41 per cent line and 95.03
per cent branch coverage.

Trivy 0.69.3, using its refreshed 10 August database, reported zero High or
Critical findings in each finished local image: API, web, PostgreSQL 17.10,
Camunda 8.9.14 and ClamAV 1.5.3. No ignore file or vulnerability exception was
used. The relevant final image identities were:

| Image | Local image identity | High | Critical |
|---|---|---:|---:|
| API | `sha256:4da1772874878f163db8aeea5e8f8c630302ae0c02c05d24b5398ac8d71d5ee7` | 0 | 0 |
| Web | `sha256:44bc3f3d339453e080e0a98e6580d05ce7c2b0cee984bb171740b77f667803ee` | 0 | 0 |
| PostgreSQL | `sha256:df0ccbdf138bbef48d80b43aae6dde1002a92b272801880327a5746485d9de6d` | 0 | 0 |
| Camunda | `sha256:f521ca02d756763c8eb65b60ccfedf9694756112216e78983e0e7793963ce1ab` | 0 | 0 |
| ClamAV | `sha256:7f48a18200a481016b882dbca2e25cd0742f3fdd2f84f1e4524b44cb400cf63e` | 0 | 0 |

The API runtime moved from an unfixed Debian 12 base to digest-pinned Ubuntu
24.04 and runs Python 3.12.3 as UID 10001. PostgreSQL now uses a digest-pinned
Alpine 3.23 runtime as the image's real `postgres` identity (UID/GID 70), with
checksum-pinned pgvector 0.8.1 compiled in a discarded build stage; the unused
`gosu` helper is absent. The live retained-data stack was recreated on those
images and remained healthy at migration 0029, with all ten request-search
projections in `READY` state. This current evidence covers
the explainable request-matching capability and controlled intake contract. The
dated SBOM, secret, Semgrep and ZAP records below were not regenerated and remain
tied to their stated candidates.

The retained development volume predates the final Alpine runtime and still
records a glibc collation version. All collation-dependent indexes were rebuilt,
but a logical dump and restore into a fresh Alpine volume remains a documented
release-evidence gate. This does not affect fresh installations or the clean
component and migration rehearsals, and no unsupported system-catalog edit was
used to hide the warning.

## Current remediation candidate, 9 August 2026

This section applies to the current `codex/product-evolution` and `main` source.
Local evidence is supplemented by the successful hosted
[CI run](https://github.com/ShabalalaWATP/Reon/actions/runs/31320684197),
[container-validation run](https://github.com/ShabalalaWATP/Reon/actions/runs/31320684213)
and [root-Compose Dependabot run](https://github.com/ShabalalaWATP/Reon/actions/runs/31320687116).
It is not a production assessment. The product owner excluded replacement of the
synthetic MVP authentication model and GitHub branch protection. Neither
exclusion was changed or counted as remediated.

### Source, dependency and secret controls

| Control | Current result |
|---|---|
| Ruff and MyPy | Ruff format/check passed 421 Python files; MyPy passed 250 source files |
| Bandit | 38,945 lines across API source and migrations, zero low, medium or high finding and zero `nosec` line |
| Semgrep | Digest-pinned scanner ran 533 applicable default and security-audit rules across 631 current-source targets with zero finding. The broader ruleset initially exposed 12 package-manager cooldown and trust-policy gaps; those controls are now enforced. One inline suppression remains limited to a SHA-256 database lookup key that Semgrep's Flask rule incorrectly treats as an HTTP response; the preceding comment states the boundary |
| Python dependency audit | Locked all-group export, including runtime, development and test tools, passed strict `pip-audit` with no known vulnerability |
| Node dependency audit | Full `pnpm audit`, including build and test tooling, passed at high severity with no known vulnerability |
| Package resolution policy | A frozen pnpm 10.34.5 installation verified the existing lock against seven-day age, trust-downgrade and transitive-source controls. uv locks with a seven-day cutoff; Dependabot applies the same cooldown to all ten configured ecosystems without delaying security updates |
| Current-source secret scan | Digest-pinned Gitleaks 8.30.0 scanned the exact staged tracked-file inventory with no leak; the inventory is retained beside the redacted report |
| Reachable-history secret scan | Digest-pinned TruffleHog 3.96.0 reported one unknown synthetic historical URI fixture. The gate accepted only its stable SHA-256 fingerprint, reason and 9 February 2027 expiry; verified findings can never be excepted and stale exceptions fail |
| Repository automation | Dependabot alerts, automated security updates, secret scanning, push protection and private vulnerability reporting are enabled. Scheduled npm, native uv, GitHub Actions, eight-Dockerfile and root-Compose updates are source controlled. The root-Compose updater ignores only five locally built output tags and continues to manage the external Python image; a contract test protects this boundary |
| Workflow validation | Digest-pinned Actionlint passed the GitHub workflows. Weekly execution, explicit deadlines, OpenAPI contract validation, current-source and reachable-history secret gates, and bounded evidence uploads are source controlled |

### Application quality gates

| Suite | Current result |
|---|---|
| Backend | 880 tests passed in 301.51 seconds; 98.84 per cent line and 95.19 per cent branch coverage |
| Frontend | 89 suites and 288 tests passed; 99.49 per cent line, 95.06 per cent branch and 96.68 per cent function coverage |

The backend duration is the complete local regression suite, not elapsed time
for a service request to move through Camunda. Both application suites exceed
the repository's separate 95 per cent line and branch gates.

### Container and runtime controls

Trivy 0.69.3 used its current 9 August vulnerability database. The first web
scan correctly exposed 11 fixed high Alpine findings in the old pinned Nginx
digest. Nginx was updated to digest-pinned 1.31.3 Alpine, rebuilt and rescanned.
The accepted result is:

| Image | Local image identity | High | Critical | CycloneDX components |
|---|---|---:|---:|---:|
| API | `sha256:6c23ecdc83028eca53b699ca3d3183dda3ac54e1c7ab4659863ff03f5c9f31d2` | 0 | 0 | 81 |
| Web | `sha256:300c3ee88acf38b70e5498fbf245109aa67cd86d5fb33dce6ddd09a0aa3866f0` | 0 | 0 | 72 |
| PostgreSQL 17.10 | `sha256:d9197bc86a9731cd8924502cf58c327a66e3fafcc903981c220562ed7fa5ca1e` | 0 | 0 | 46 |
| Camunda 8.9.14 | `sha256:bb785638d50cbaeb3ef4bf2b56495fd00e5bd4e4e28f2d72b96d1a07499cd017` | 0 | 0 | 607 |
| ClamAV 1.5.3 | `sha256:8d50eaff33d6fcac14f1beb579ee9fe7ae132738d8154a6619f7ef7dd6154244` | 0 | 0 | 42 |

The fresh QA runtime then proved:

- PostgreSQL 17.10 ran as UID 70, read-only with all capabilities dropped, and
  contained no `gosu` executable.
- API and worker ran as UID 10001 with read-only roots, no capabilities and no
  `pip` or `uv` executable. API, worker and migrator consume the same scanned
  image rather than three project-specific copies.
- Camunda ran as UID 1001 with all capabilities dropped; the unused SQL Server
  JDBC driver, `tar`, `wget` and `libnghttp2` files were absent.
- Nginx 1.31.3 ran as UID 101 with a read-only root, no capabilities and its PID
  and temporary files under `/tmp`. Both `/run` and `/var/run` upstream PID
  layouts are covered by the build assertion.
- Clamd and its separate updater ran as UID 100 with read-only roots, no
  capabilities and no-new-privileges. Clamd had only the internal scanner
  network and a read-only definition mount; the non-scanning updater alone had
  the outbound signature network and writable mount.
- ClamAV loaded daily definition version 28087, matching the current file on
  disk. FreshClam reported the configured mirror databases current. Health uses
  the database's signed build timestamp rather than filesystem modification
  time. A stale signed database was touched to the current time and still failed.
- A live clamd external-DNS/egress probe was denied. The updater's FreshClam log
  proved successful access to the configured ClamAV mirror.
- Every image produced a valid non-empty CycloneDX document. CI repeats the five
  high/critical gates and retains the five SBOMs as one release artefact.

### Dynamic and workflow verification

- Current ZAP stable digest
  `sha256:781a2bdaea47324e7bab583e2263f21d257b0aee61ed51521a5be45f5f5081ef`
  ran against the local synthetic QA stack.
- The passive web baseline discovered nine URLs and produced zero failure across
  65 rules. Its two warnings were expected cacheable hashed assets and SPA
  identification. `index.html` revalidates and API responses are `no-store`.
- The OpenAPI-driven active API scan imported 141 operations, exercised 242 URLs
  and passed all 119 reported rules with zero failure, warning or information
  finding. The local rate rows created by the authorised scan were removed
  afterwards.
- QA readiness returned 200 with database, workflow, configuration and
  maintenance all `ok`. Existing invalid legacy evidence was not fabricated;
  both old synthetic databases were dumped before the disposable QA volumes were
  reset and the first-start governed lifecycle created valid current evidence.
- A real PostgreSQL fixed-window probe across independent sessions returned
  `true, true, false` for a source limit of two and a bounded retry interval.
- Login-budget persistence now completes in a separate cancellation-shielded
  transaction. Tests proved an independent session can read the attempt and a
  second limiter transaction can finish while password hashing is deliberately
  blocked; cancellation waits for the durable operation.
- Connection acquisition and the complete limiter operation are bounded to three
  seconds, with 2.4-second transaction-local PostgreSQL statement and lock
  deadlines. A live transaction held the global row lock: login returned the
  account-neutral `503` in 2.49 seconds, no session was created, and a correct
  login plus logout succeeded after release.
- PostgreSQL reached `0021_schema_metadata`; `alembic check` reported no model
  drift. The constraint-name alignment migration downgraded to 0020 and upgraded
  to head again while the application was stopped, then remained drift-free.
- Camunda completed the staffed JOCK → ACSA-B Ops → SSG Team route, including
  two clarification loops, and the selectable SYGOC → Nimbus Ops → Beacon Team
  route. Both finished at release.
- API and Nginx returned opener, embedder and resource isolation headers. API
  responses were `no-store`; Nginx revalidated the SPA index.

### Remaining acceptance boundary

These results remove the reported source, dependency, image, scanner-freshness,
rate-limit, documentation-surface, header, readiness and scan-noise findings.
They do not provide production identity, an edge WAF, TLS/HSTS termination,
private production Camunda authentication, production object storage/CDR,
signed provenance, IaC/admission policy, a joined production recovery exercise
or an independent penetration test. Those remain explicit production gates.

## Current-source static verification, 8 August 2026

The runtime-hardening source passed Bandit across API source and migrations
with no low, medium or high finding and no `nosec` suppression. The locked
Python environment and Node dependency tree reported no known vulnerability;
the editable first-party package was the only non-PyPI audit exclusion. MyPy,
Ruff, Vulture, Knip, TypeScript, ESLint, licence and repository contract gates
also passed. These are current source and dependency results, not a claim that
the historical image or secret-scan artefacts below were regenerated.

## Historical release-candidate results

Historical candidate evidence recorded on 7 August 2026 against the working tree
that existed on that date. It is not a claim about the current candidate.

| Control | Result |
| --- | --- |
| Bandit | Current API source scanned, no low, medium or high issue; no `nosec` suppression |
| Python dependency audit | Local locked environment, excluding only the editable first-party package, no known vulnerability |
| Node dependency audit | Production dependencies, no known vulnerability at high threshold |
| Licence gate | Two Node licence groups and 82 Python packages passed; reviewed Camunda and first-party metadata exceptions documented |
| API image | A refreshed Trivy 0.68.2 database exposed high and critical findings in the former Debian 12 base. The runtime was moved to digest-pinned Python 3.12 on Alpine 3.23; the rebuilt image reported zero high or critical findings |
| Web image | Initial Trivy scan found 11 fixed Alpine high findings; the nginx runtime now applies repository security upgrades and the rebuilt image reported zero high or critical findings |
| Source secret scan | Pinned Gitleaks 8.30.0 scanned the dedicated source inventory, including docs and tests but excluding `.env`, caches, browser profiles and generated output; 2.71 MB scanned with no leak found |
| PostgreSQL bootstrap | Migration, runtime, backup and Camunda identities were non-superuser, non-creator roles with isolated database access; read-only backup write denial passed |
| CI static analysis | Pinned CodeQL security-extended jobs exist for Python and JavaScript/TypeScript |
| Git history secret scan | Digest-pinned TruffleHog 3.96.0 scanned reachable Git history with zero verified or unknown secret locally and in GitHub Actions run `31169475483` |
| CI image scan | Pinned Trivy high/critical gates exist for API and web images; execution awaits the CI baseline |

The reproducible source scan is `docker build --file
scripts/secret-scan.Dockerfile --target evidence --output
type=local,dest=output/security .`. A Dockerfile-specific ignore policy prevents
the application-image exclusions from hiding documentation or tests while
excluding generated browser profiles and other non-source evidence. The scanner
image is digest-pinned and the output SHA-256 was
`37517E5F3DC66819F61F5A7BB8ACE1921282415F10551D2DEFA5C3EB0985B570`.
Gitleaks 8.30.0 is deliberately retained because the 8.30.1 default-rule
regression remains open upstream.

The Git-history gate is `docker build --file
scripts/trufflehog-scan.Dockerfile --target gate .`. It copies only `.git` into
the digest-pinned scanner, avoiding generated files and Docker Desktop bind-mount
behaviour. The final local run scanned 513 chunks and 2,828,642 bytes with zero
verified and zero unknown finding. The pinned hosted job also passed against
`origin/main` in GitHub Actions run `31169475483`.

The final API and web reports are retained as
`output/security/trivy-api-final.txt` and
`output/security/trivy-web-final.txt`. Their SHA-256 values are respectively
`6566663D5AF4FC2737457F56D3107B6B2081783C6F43D582E689A09705B7818A`
and
`9F13B6382956133329C5519500E00AF0C197AF3847F150D6A5E51BB4555E15C9`.
