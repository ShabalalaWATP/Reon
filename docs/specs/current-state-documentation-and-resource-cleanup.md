# Current-state documentation and resource-cleanup specification

Status: implemented and verified
Last reviewed: 14 August 2026

## Objective

Provide one coherent, current description of Mist Service and eliminate the
SQLite resource warning found during the maintainability candidate verification.
Current-state guides must describe executable code and supported deployment
paths, not removed implementation details.

## Requirements

| ID | Requirement | Acceptance evidence |
| --- | --- | --- |
| DOC-01 | The root README explains the current product, workflow, roles, technology stack, security model and operational boundary | Documentation review and link gate |
| DOC-02 | The architecture guide describes the current frontend, API, worker, PostgreSQL, Camunda, storage, scanner, context, conversation and package boundaries | Source-to-document inventory and architecture review |
| DOC-03 | Structurizr DSL is the source for current C4 system-context, container, component and deployment views | Structurizr workspace validation and documented rendering command |
| DOC-04 | Windows, macOS and Linux setup paths contain verified prerequisites, commands, health checks and troubleshooting | Host setup guide and documentation link gate |
| DOC-05 | AWS and GCP guides distinguish the supported synthetic single-host evaluation from unimplemented production adapters | Cloud guide review against deployment boundaries |
| DOC-06 | Current-state guides do not instruct readers to use files, interfaces or modules removed from the repository | Repository-wide current-document reference audit |
| DOC-07 | Dated ADR and assurance records are labelled as decision or evidence history and are not presented as current setup instructions | Documentation home and navigation policy |
| RES-01 | Every directly opened SQLite connection in the quarantine-index regression closes deterministically | Warning-as-error product-storage test |
| RES-02 | Resource and unraisable-exception warnings fail the backend test suite | Pytest warning policy |

## Current documentation boundary

The following are current-state authorities and must agree with executable
source: the root README, documentation home, user stories, system architecture,
workflow guide, organisation guide, role matrix, deployment guides, operations
runbooks and current security guidance.

The development story remains chronological. ADRs retain accepted decision
context, and assurance records retain dated evidence. They may name an earlier
state only when clearly identified as historical and must link readers back to
the current-state authority.

## Verification

- run the documentation duplication and link checks;
- validate the Structurizr workspace;
- search current-state guides for removed source paths and outdated migration or
  test figures;
- run product-storage tests with resource warnings treated as errors;
- run Ruff, MyPy, the backend suite and the repository quality gate; and
- verify the active synthetic stack reports healthy application dependencies.

## Verified result

- the official Structurizr CLI 2025.11.09 validated the workspace;
- documentation duplication, link and current-source-reference gates passed;
- the focused storage regression passed with warnings treated as errors;
- the complete backend suite passed 1,318 tests with 13 skips and no resource
  warning at 98.73 per cent line and 95.00 per cent branch coverage;
- all 490 frontend tests passed at 98.80 per cent line and 95.04 per cent branch
  coverage; and
- the root repository quality gate passed.
