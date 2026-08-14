# Role and permission matrix

Status: current application permissions with production boundary decisions identified
Last reviewed: 14 August 2026

## Enforcement principles

- FastAPI checks active identity, role, organisational scope, object relationship
  and workflow state for every read and mutation.
- React navigation and filtered choices are usability controls only.
- Camunda candidate groups do not grant application data access.
- Effective workspace membership and its Manager or Member position are
  independent of the representative workflow role.
- Platform administration is metadata-only and grants no request or product
  content access.
- Denials avoid confirming whether an out-of-scope object exists.
- An account with dual capability acts in one explicit Customer or Staff context;
  switching context rotates session and CSRF proof and clears protected client state.

## Application permissions

| Actor | Permitted action | Required scope and state | Object/action check | Separation and audit |
|---|---|---|---|---|
| Authenticated user | Maintain their profile | Own active account | Subject is always the authenticated user | Profile changes remain attributable; bounded personal fields do not enter workflow or analytics |
| Customer | Create and submit a request | Own authenticated account; every submission field valid | Requester ID becomes immutable ownership | Submission audited without narrative in admin telemetry |
| Customer | Track, answer clarification, download and give feedback | Own request; matching workflow state; released product for download | Ownership and action-state check on every request | Download and feedback events attributable to Customer |
| Dual-capability account | Switch between Customer and Staff context | Context appears in server-calculated available contexts | New session generation, CSRF rotation and context-scoped cache reset | Staff authority cannot be used on the actor's own Customer request |
| CRIOC Routing User | Review, request information, close or choose a Command | Active CRIOC candidate group and personally claimed task | Destination must be an effective direct Command child | Manager and Member use the same claim-based routing action; no product approval |
| Request Coordination User | Choose an Ops group, return, hold or close | Active candidate group for the selected Command and personally claimed task | Destination must be an effective direct Ops-group child | Manager and Member use the same action; no team or Analyst selection |
| Ops Routing User | Choose a delivery team or return | Active candidate group for the selected Ops group and personally claimed task | Destination must be an effective direct team child | Manager and Member use the same action; unstaffed choice remains explicit |
| Workspace Member | Create, edit and cancel personal calendar activity | Current effective membership in the exact unit | Subject is always the authenticated user; no request link or alternate subject accepted | Private detail is redacted from shared views |
| Workspace Member | View a colleague's bounded team profile | Authorised read access to the exact workspace; subject has membership history in that workspace | Exact team and subject relationship checked on every read | Service number and free-form personal notes are excluded; inaccessible records are not disclosed |
| Routing Manager | Maintain exact-unit Members and unit events | Current Manager position and exact management grant | No parent, child or sibling management and no ticket commitment | Does not add routing approval or assign routing tasks |
| Team Manager | Assign one Lead and up to ten Contributors and review submitted work | Exact active team membership and candidate group; claimed task | Every participant must be a current Member of that exact team | Assignment reason, history and approval/rework outcome audited |
| Team Manager | Manage roster, board and team calendar | Current exact-team Manager position and exact active management grant | Position, grant, membership state and optimistic revision checked | Membership and planning events attributable and reversible |
| Team Manager | Send a task hastener to one or all assigned Analysts | Current Manager position; locked current request is in active production and assigned to the exact team | Recipients are server-resolved current Leads and Contributors who are active exact-team Delivery Specialists; every recipient projection is required | Reminder is mandatory-notified and stored in Customer-visible tamper-evident request history; ownership, assignments and Camunda state do not change |
| Assigned Team Analyst | Produce, converse, revise and submit a product package | Current Lead or additional assignment and active exact-team membership | Same production controls for every assigned Analyst; package state and expected revision checked | Lead remains the accountable badge; every mutation retains its actual actor |
| QC Team Manager, reviewer | Review, return or approve a product | Active QC group, personally claimed quality task and matching package state | Exact Team-Manager-approved package | Cannot disseminate the package they reviewed |
| QC Team Manager, releaser | Disseminate or withdraw a product | Active QC group, personally claimed release task and ready-for-release package | Exact approved package and Customer relationship | Must be a different person from QC reviewer; Manager approval cannot substitute for QC release |
| Authorised request participant | Send a structured conversation message | Server-calculated target among Customer, current owner, Team Managers, assigned Analysts, route unit or QC Team | Request scope, active context, target and visibility checked on every read/write | Immutable author, context, audience, time, delivery and read state |
| Platform Administrator | Manage accounts, profiles, memberships and safe configuration metadata | Active Platform Administrator and fresh step-up for sensitive changes | Dedicated metadata schemas and action checks | No implicit request/product access; tamper-evident admin audit |
| Platform Administrator | Change the global visual classification marking | Active Platform Administrator, CSRF and fresh step-up | Exact singleton and expected version | New value and actor recorded in the administration audit chain |
| Platform Administrator | Receive a password-assistance notification | Active Platform Administrator | A submitted email matched an active account after shared rate limits | Notification identifies the account but never stores the submitted email in the attempt record |
| Configuration Approver | Approve or reject proposed changes | Platform Administrator, fresh step-up, proposal awaiting approval | Must not be proposal creator; exact immutable revision | Reason and reviewed revision recorded |
| Workflow Operator | Deploy a compatible Camunda definition | Operator-controlled deployment boundary, outside ordinary application role | Compatibility key, process identity and checksum attested | Cannot approve configuration or obtain product content |
| Support Operator | Inspect health and content-free diagnostics | Named operational authority; no implicit application role | Correlation, status and aggregate metadata only | Elevated diagnostics and recovery actions recorded |

## Routing visibility

| Scope | May see request content | May track progress | May route | May approve product | May administer configuration |
|---|---:|---:|---:|---:|---:|
| Customer owning request | Yes | Yes | No | No | No |
| CRIOC on selected path | Operationally required fields | Yes | CRIOC task only | No | No |
| Selected Command | Operationally required fields | Yes | Command task only | No | No |
| Selected Ops group | Operationally required fields | Yes | Ops task only | No | No |
| Selected delivery team | Yes | Yes | Manager assigns within team | Manager review only | No |
| QC function | Approved-candidate content | Yes | Quality or release outcome only | Separate QC review and dissemination claimants | No |
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
