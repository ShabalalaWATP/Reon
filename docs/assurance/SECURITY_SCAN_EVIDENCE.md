# Security scan evidence

## Local results

Recorded on 7 August 2026 against the current working tree.

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
| Git history secret scan | Digest-pinned TruffleHog 3.96.0 scanned 513 chunks and 2.83 MB of reachable Git history with zero verified or unknown secret; the matching hosted CI job awaits a remote |
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
verified and zero unknown finding. This is local evidence; the equivalent hosted
CI job still awaits a remote and is not represented as having run.

The final API and web reports are retained as
`output/security/trivy-api-final.txt` and
`output/security/trivy-web-final.txt`. Their SHA-256 values are respectively
`6566663D5AF4FC2737457F56D3107B6B2081783C6F43D582E689A09705B7818A`
and
`9F13B6382956133329C5519500E00AF0C197AF3847F150D6A5E51BB4555E15C9`.
