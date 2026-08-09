# Role and permission matrix

Status: implemented MVP roles with enterprise boundary decisions identified
Last reviewed: 8 August 2026

## Enforcement principles

- FastAPI checks active identity, role, organisational scope, object relationship
  and workflow state for every read and mutation.
- React navigation and filtered choices are usability controls only.
- Camunda candidate groups do not grant application data access.
- Platform administration is metadata-only and grants no request or product
  content access.
- Denials avoid confirming whether an out-of-scope object exists.

## Application permissions

| Actor | Permitted action | Required scope and state | Object/action check | Separation and audit |
|---|---|---|---|---|
| Customer | Create and submit a request | Own authenticated account; every submission field valid | Requester ID becomes immutable ownership | Submission audited without narrative in admin telemetry |
| Customer | Track, answer clarification, download and give feedback | Own request; matching workflow state; released product for download | Ownership and action-state check on every request | Download and feedback events attributable to Customer |
| JIOC Routing User | Review, request information, close or choose a Command | Active JIOC candidate group and claimed task | Destination must be an effective direct Command child | Claim and outcome recorded; no product approval |
| Command Routing User | Choose an Ops group, return, hold or close | Active candidate group for the selected Command and claimed task | Destination must be an effective direct Ops-group child | Human outcome recorded; no team or analyst selection |
| Ops Routing User | Choose a delivery team or return | Active candidate group for the selected Ops group and claimed task | Destination must be an effective direct team child | Human outcome recorded; unstaffed choice remains explicit |
| Team Manager | Assign an Analyst and review submitted work | Exact active team membership and candidate group; claimed task | Analyst must have active membership in that exact team | Assignment and approval/rework outcome audited |
| Team Manager | Manage roster, board and team calendar | Exact active management grant for the team | Grant, membership state and optimistic revision checked | Membership and planning events attributable and reversible |
| Team Analyst | Produce, revise and submit a product package | Assigned request and active exact-team membership | Assignment, package state and expected revision checked | Immutable package history retained |
| QC Manager | Review, return, disseminate or withdraw a product | Active QC group and matching workflow/package state | Exact approved package and Customer request relationship | Manager approval cannot substitute for QC release |
| Platform Administrator | Manage accounts, profiles, memberships and safe configuration metadata | Active Platform Administrator and fresh step-up for sensitive changes | Dedicated metadata schemas and action checks | No implicit request/product access; tamper-evident admin audit |
| Configuration Approver | Approve or reject proposed changes | Platform Administrator, fresh step-up, proposal awaiting approval | Must not be proposal creator; exact immutable revision | Reason and reviewed revision recorded |
| Workflow Operator | Deploy a compatible Camunda definition | Operator-controlled deployment boundary, outside ordinary application role | Compatibility key, process identity and checksum attested | Cannot approve configuration or obtain product content |
| Support Operator | Inspect health and content-free diagnostics | Named operational authority; no implicit application role | Correlation, status and aggregate metadata only | Elevated diagnostics and recovery actions recorded |

## Routing visibility

| Scope | May see request content | May track progress | May route | May approve product | May administer configuration |
|---|---:|---:|---:|---:|---:|
| Customer owning request | Yes | Yes | No | No | No |
| JIOC on selected path | Operationally required fields | Yes | JIOC task only | No | No |
| Selected Command | Operationally required fields | Yes | Command task only | No | No |
| Selected Ops group | Operationally required fields | Yes | Ops task only | No | No |
| Selected delivery team | Yes | Yes | Manager assigns within team | Manager review only | No |
| QC function | Released-candidate content | Yes | Release outcome only | Final QC and dissemination | No |
| Platform Administrator | No | No content-bearing tracking | No | No | Yes |

## Configuration action detail

Application roles and operational authorities are deliberately separate. A
Platform Administrator is an application role. Workflow Operator, Support
Operator and recovery authority are production operating-model decisions and do
not arise from holding that application role.

| Action | Platform Administrator | Configuration Approver | Workflow Operator | Support Operator |
|---|---:|---:|---:|---:|
| Read configuration and content-free history | Yes | Yes | Deployment metadata only | Health metadata only |
| Prepare or alter proposed changes | Yes, after step-up | No while acting as reviewer | No | No |
| Validate proposed changes | Yes, after step-up | Read result | No | No |
| Submit for review | Creator only | No | No | No |
| Approve or reject | No for own proposal | Yes, different actor and fresh step-up | No | No |
| Activate approved changes | Authorised administrator after step-up | No implicit right | No | No |
| Alter current or historical components | No | No | No | No |
| Deploy vetted BPMN | No implicit right | No | Yes, through controlled deployment | No |
| Attest compatible deployed process identity | No implicit right | No | Yes | Read-only diagnosis |
| Apply database recovery | No implicit right | No | No | Named recovery authority only |
| Read request or product content | No by these authorities | No | No | No |

The interface may hide unavailable actions, but every row is enforced again by
FastAPI and, for sealed snapshots and workflow identity, PostgreSQL.

## Enterprise decisions still required

- Map application roles to production identity-provider groups and privileged
  access workflows.
- Name approver, workflow-operator, support and emergency recovery owners.
- Define joiner, mover, leaver, periodic access review and break-glass policy.
- Decide whether confusable Unicode organisation names are rejected or require
  secondary review.
