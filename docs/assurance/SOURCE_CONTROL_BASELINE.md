# Source control baseline evidence

## Reviewed local baseline

Recorded on 7 August 2026. The initial local source baseline is:

| Property | Value |
| --- | --- |
| Branch | `main` |
| Root commit | `cdfea322d13e8812ee82aae377dd58b419247e54` |
| Tree | `4dbe5bf6a9d470af2067be7be16603a32bc897e2` |
| Subject | `feat: establish ISTARI Service MVP baseline` |
| Parents | None, this is the repository root commit |
| Inventory | 445 files, 65,110 inserted lines |

The baseline was created only after staged whitespace review, generated-file
inventory review, a digest-pinned current-tree Gitleaks scan, full backend and
frontend coverage gates, workspace quality gates and live-system assurance.

The first prospective commit exposed six TruffleHog Lob-detector false
positives caused by test function names that were exactly 40 characters long.
Those names were changed and the unpublished root commit was amended. The final
reachable history contains none of those detector matches.

## History secret gate

The reproducible gate is:

```powershell
docker build --file scripts/trufflehog-scan.Dockerfile --target gate .
```

It uses digest-pinned TruffleHog 3.96.0 and copies only `.git` into the scanner
image. The final run scanned 513 chunks and 2,828,642 bytes, finding zero
verified and zero unknown secrets.

## Approved remote and hosted verification

The Repository Owner directed publication to
`https://github.com/ShabalalaWATP/Reon`. The repository visibility is `PUBLIC`.
That visibility is recorded explicitly because private remains the default for
new projects. This repository contains only synthetic, public-safe material and
both current-tree and history secret gates passed before publication.

Commit `47a0a6b6d3d331822c06cc7627d07ff125c5355a` was pushed to `origin/main`.
GitHub Actions run `31169475483` completed successfully, including backend and
frontend coverage, CodeQL, secret scanning, dependency and licence audits,
PostgreSQL bootstrap, container builds, Trivy scans and the bounded Camunda
smoke. DOD-01 is evidence-ready.
