# Configuration and routing evidence

Status: local automated and Chromium journey evidence recorded, not accepted
Revision: uncommitted working tree based on
`9f520ba4cb2d648a5730b6420e63e956adac10d5`; no immutable candidate exists yet

Scope note: search, breadcrumb and filtered-parent evidence in this record is
for the Platform Administrator configuration workspace. The native human
routing control uses an unranked direct-child list. HRU-02 route context and
HRU-03 literal direct-child destination search were added on 8 August 2026;
representative acceptance remains open.

## Implemented controls under test

- Task-oriented `Current configuration` and `Proposed changes` presentation.
- Immediate selection of newly created proposed changes after registry refresh.
- Literal name, stable-code and humanised-kind hierarchy search.
- Search result count, ancestor context, no-result state and filtered keyboard
  navigation.
- Root-to-selected-unit keyboard breadcrumb.
- Effective-time, routing-state and exact-kind parent filtering for create/move.
- Canonical reminder comparison and change-only staffing preview.
- Existing immutable revision, expected-revision, validation, independent review,
  effective-date, activation and in-flight pinning controls remain intact.

## Automated evidence recorded

| Check | Result | Notes |
|---|---|---|
| Focused Vitest configuration components and journey | 21 passed | Search, breadcrumb, filtered parents, scheduled retirement, creation selection, review and activation terminology |
| Full Vitest suite | 257 passed | 99.60% line and exact 95.02% branch coverage |
| Full pytest suite | 804 passed | 13,614/13,768 lines (98.8815%) and 2,444/2,572 branches (95.0233%) |
| Repository static and policy gates | Passed | Quality-gate tests, line limit, terminology, operations contract, licence policy, TypeScript and ESLint |
| Production frontend build | Passed | 2,023 modules transformed by Vite after TypeScript build |
| OpenAPI contract | Passed | Administration, hierarchy, routing, tracking and product download |
| BPMN and Camunda mock contract | Passed | 11 user tasks, 10 gateways, 35 flows, complete diagram data and alternative-team contract |
| Component axe check | Passed in configuration journey | Full browser/manual accessibility remains open |
| Rebuilt-stack Chromium journey | Passed | Current/proposed language, unchanged preview, SSG ancestor-preserving search, CRIOC-to-SSG breadcrumb, exact-kind move-parent options and a clean post-login console |
| Fresh PostgreSQL 17 migration and guard check | Passed | Empty-to-0018 startup, 73 users, equal non-zero approval/activation digest, sealed snapshot controls and denial of forged approval/activation inserts |

## Reproducibility record

The final local gates used Python 3.13.3, Node 22.20.0 and pnpm 11.16.0 on
Windows. Principal commands were `pnpm check`, `uv run --directory apps/api
pytest`, `pnpm --filter @istari-service/web test`, `pnpm --filter
@istari-service/web build`, Ruff format/check, MyPy, Bandit, the OpenAPI contract,
the Camunda smoke contract and both BPMN validator suites.

Local SHA-256 evidence artefacts:

| Artefact | SHA-256 |
|---|---|
| `apps/api/coverage.json` | `8656EB9183FC60800D5012090B3AF4DF655923DCCCBB174BAA97D49CE4F94C21` |
| `apps/web/coverage/coverage-summary.json` | `B6C52565626301DD89BABFC35CFFE98E3E44B6F520BAAAE261D1E850DEEE38AA` |
| `workflow/service-request.bpmn` | `4FB7167BC69744A22EFB1C19FF2F84D086A35E4CE10CD416D221DBA0A09023C5` |

The default-off local stack returned HTTP 200 for health/readiness and a final
admin login had no console error. Its configuration route correctly redirected
because configuration administration was disabled. The enabled rebuilt-stack
journey above is the applicable configuration-browser evidence. Evidence must
be regenerated and attached to a commit before acceptance.

## Evidence still required

- Live browser creation/selection and activation journey against a disposable
  dataset. The selection behaviour is covered by the automated journey test.
- 390-pixel, 200% zoom, reduced-motion and keyboard-only review.
- Current Chrome, Edge and Firefox evidence.
- Live PostgreSQL one-winner activation concurrency evidence. Forged-parent and
  stale-result behaviour is covered automatically but still requires live UAT.
- Large hierarchy search performance at the specified 2,000-unit fixture.
- Live Camunda alternative-branch and unstaffed-team routing evidence.
- Named product, security, operational and representative-user acceptance.
- Native routing breadcrumb and bounded direct-child destination search, with
  keyboard, non-enumeration and no-ranking evidence.

Nothing in this record authorises production use or closes detailed capability
Definition of Done gates without the missing evidence and named acceptance.
