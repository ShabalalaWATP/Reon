# Configuration administration usability

Status: implementation in progress
Owner: Platform administration
Last reviewed: 8 August 2026

## Purpose

Make organisation-routing changes understandable and efficient without weakening
the immutable, independently approved configuration control. Operator language
must describe the task being performed rather than expose persistence terms such
as `version` or `draft`.

## Product language

The interface uses these terms:

| Internal state | Operator language |
|---|---|
| Active configuration | Current configuration |
| Draft configuration version | Proposed changes |
| Validated version | Ready for review |
| Awaiting approval | Awaiting approval |
| Superseded version | Previous configuration |
| Rejected version | Rejected changes |

Internal API fields and database records retain their existing names because
they provide optimistic concurrency, immutable history and request pinning.

## Experience thesis

- Visual thesis: a calm, dense administration workspace where the organisation
  path and change state are always visible.
- Content plan: current or proposed configuration context, searchable hierarchy,
  selected-unit editor, bounded workflow settings, then preview and approval.
- Interaction thesis: search retains ancestor context, breadcrumb selections
  move focus predictably, and parent choices update immediately when unit kind
  changes.

## Roles and boundaries

- A Platform Administrator may inspect configuration history and prepare changes
  after step-up authentication.
- A different Platform Administrator must approve the exact validated change set.
- A Platform Administrator has no implicit access to service-request content.
- Ordinary routing users and Customers cannot access configuration administration.
- The interface cannot add workflow stages or arbitrary executable outcomes.

## Complex user stories

### CAU-01: Locate a unit in a large organisation

As a Platform Administrator supporting hundreds of units, I need to search by
display name, stable code or unit type so that I can find a unit without scanning
the entire hierarchy.

Acceptance criteria:

1. Search is case-insensitive and ignores leading or trailing whitespace.
2. Results retain every ancestor required to understand their location.
3. The result count is announced and a clear empty state is shown.
4. Clearing search restores the complete hierarchy and keyboard navigation.
5. Search does not reveal units the administrator is not authorised to inspect.

### CAU-02: Understand organisational context before editing

As a Platform Administrator editing similarly named teams, I need a breadcrumb
from the root to the selected unit so that I do not change the wrong branch.

Acceptance criteria:

1. The path reflects the proposed structure, including unsaved-navigation focus.
2. Each ancestor is a keyboard-operable button that selects and focuses that unit.
3. The breadcrumb has an accessible label and does not rely on colour alone.
4. Orphaned or invalid imported records degrade to the selected unit safely.

### CAU-03: Create a structurally valid unit

As a Platform Administrator, I need the parent selector to offer only compatible
parents so that invalid hierarchy combinations cannot be proposed accidentally.

Acceptance criteria:

1. A Command can be placed only beneath the root.
2. An Ops group can be placed only beneath a Command.
3. A delivery team can be placed only beneath an Ops group.
4. Retired or ineffective parents are excluded at the proposed effective time.
5. Changing the child kind clears an incompatible parent selection.
6. Server-side validation remains authoritative and rejects forged requests.

### CAU-04: Move a unit without creating a cycle

As a Platform Administrator, I need move destinations constrained by unit kind
and hierarchy so that I cannot create a cycle, skip a routing level or select the
unit itself.

Acceptance criteria:

1. Only parents of the immediately preceding kind are listed.
2. The selected unit, inactive records and descendants are excluded.
3. Existing effective-dated history is retained.
4. The preview identifies the old and new organisational context.
5. Repeating a move within one proposal replaces its provisional edge rather
   than creating a zero-length effective interval.

### CAU-05: Prepare changes without configuration jargon

As an occasional Platform Administrator, I need task-oriented labels so that I
can distinguish the live configuration from proposed changes without learning
the persistence model.

Acceptance criteria:

1. The page does not present `version` or `draft` as the primary operator concept.
2. Current and proposed configurations are visibly distinct.
3. Creating proposed changes selects the new record immediately.
4. An unchanged proposal reports no changes from the current configuration.
5. Technical sequence and concurrency values remain available to audit and API
   consumers, but are not required to operate the page.

### CAU-06: Review and approve independently

As an independent Platform Administrator, I need to review the exact validated
changes, findings, effective time and actor history so that approval cannot be
mistaken for a general authorisation.

Acceptance criteria:

1. The creator cannot approve their own proposed changes.
2. Mutation after validation invalidates the earlier review state.
3. Approval and activation require step-up authentication and a recorded reason.
4. Stale concurrency tokens return a conflict and do not overwrite newer work.
5. Activation is blocked until every configured route is valid.

### CAU-07: Preserve in-flight work

As an operations owner, I need configuration activation to affect only eligible
new requests so that an in-flight request cannot silently change route, candidate
group or workflow definition.

Acceptance criteria:

1. Every submitted request is pinned to an immutable configuration and workflow.
2. Historical paths remain readable for audit and requester tracking.
3. A renamed unit retains its stable identifier.
4. Retirement prevents new routing only from its effective time.

### CAU-08: Recover from partial or conflicting administration

As a Platform Administrator, I need clear failures and recoverable proposed
changes so that validation, network or concurrent-edit failures do not create an
unknown live state.

Acceptance criteria:

1. Failed saves leave the current configuration unchanged.
2. A stale update explains that the proposal changed and must be reloaded.
3. Activation and materialisation are transactional and auditable.
4. Restart restores the active configuration rather than fixture defaults.
5. Support can correlate UI, API, audit and Camunda events without request content.

## Human-routing user stories

These stories preserve human choice. Search, workload and staffing information
may help a person find a destination, but must never rank, recommend or select it.

### HRU-01: Route through direct children only

As a JIOC, Command or Ops Routing User, I need to see only the valid immediate
children of the current route so that I cannot accidentally skip a level.

Acceptance criteria:

1. JIOC lists effective Commands, a Command lists its effective Ops groups, and
   an Ops group lists its effective teams.
2. Every configured sibling remains selectable, including fictional seeded
   branches and an explicitly marked unstaffed team.
3. FastAPI reloads and validates the destination when the outcome is recorded.
4. Candidate-group names are never accepted from the browser.

### HRU-02: Understand the route before hand-off

Milestone status: implemented in the native routing-destination control on
8 August 2026.

As a Routing User, I need the current root-to-stage path and selected destination
summarised before submission so that similarly named units are not confused.

Acceptance criteria:

1. The path uses display names and stable codes where names are ambiguous.
2. The submit action names the human outcome and destination.
3. Keyboard and screen-reader users receive the same summary.
4. No progress-tracking ancestor gains an approval action.

### HRU-03: Find a destination at enterprise scale

Milestone status: implemented in the native routing-destination control on
8 August 2026. Configuration hierarchy search remains a separate administrator
capability.

As a Routing User in a large branch, I need literal search by name and stable code
so that every permitted sibling remains discoverable without automated ranking.

Acceptance criteria:

1. Search operates only within server-authorised direct children.
2. Matching is case-insensitive, bounded and does not interpret regular expressions.
3. No result is silently hidden by popularity, workload or inferred suitability.
4. Clearing search restores the complete permitted sibling set.

### HRU-04: Make an informed unstaffed-team decision

As an Ops Routing User, I need staffing state displayed without disabling a valid
team so that I remain accountable for the routing decision.

Acceptance criteria:

1. Minimum Manager and Analyst shortfall is explicit before submission.
2. The application does not fall back to OSG or another staffed team.
3. The tracker shows `Awaiting team staffing` until exact-team staffing exists.
4. Restoring membership progresses only through a named human action.

### HRU-05: Handle a stale destination safely

As a Routing User whose page was open during configuration activation, I need a
clear conflict rather than misrouting when the chosen destination changed.

Acceptance criteria:

1. The server validates request pin, stage, route parent and expected revision.
2. A stale or ineffective destination causes no Camunda command or partial write.
3. The user reloads the authoritative choices and makes a new human decision.

### HRU-06: Resolve competing task claims

As one of two eligible Routing Users, I need exactly one successful claim and a
safe refresh for the other user so that a request is not routed twice.

Acceptance criteria:

1. Claim and completion are one-winner operations.
2. The losing user sees the current assignee or state without protected content.
3. Retry and reconciliation do not duplicate the human outcome.

### HRU-07: Request more information without losing the route

As a JIOC Routing User or assigned Analyst, I need a stored clarification thread
so that the Customer can respond within the dashboard and routing context remains
attributable.

Acceptance criteria:

1. Only authorised participants can read message content.
2. Trackers receive state and timing metadata, not clarification text.
3. One open clarification exists at a time and sequential threads are retained.
4. Response returns to the named human stage, not an inferred destination.

### HRU-08: Track without approval authority

As JIOC, selected Command or selected Ops staff, I need scoped progress visibility
after routing so that I can coordinate work without approving the product.

Acceptance criteria:

1. Visibility follows the request's selected path and contains only tracking data.
2. Siblings, unrelated ancestors and other Customers are excluded.
3. Team Manager review and QC dissemination remain the only downstream approval
   boundaries.
4. Released Customer access is an authenticated file download or approved link.

## Non-functional requirements

- Pilot journeys meet WCAG 2.2 AA, including keyboard tree and breadcrumb use.
- Search feedback appears within 100 ms for 2,000 locally loaded units on the
  supported pilot workstation profile.
- Ordinary configuration reads target p95 below two seconds at pilot load.
- All mutations use CSRF protection, step-up authentication, object/action
  authorisation, optimistic concurrency and tamper-evident audit events.
- Review previews enumerate every distinct future effective transition and show
  its effective time. Approval and activation bind the displayed canonical
  snapshot reference.
- Non-Draft configuration components are sealed by the PostgreSQL boundary;
  application checks remain the portable first line for local SQLite tests.
- No secrets, passwords, session identifiers or request content appear in logs,
  previews, analytics or configuration exports.

## Verification

- Component tests cover search, ancestor retention, empty results, breadcrumbs
  and valid-parent filtering.
- Journey tests cover creation, selection refresh, validation, independent review
  and activation terminology.
- Browser evidence covers desktop and narrow layouts, keyboard use and automated
  accessibility checks.
- Operational routing evidence covers direct children, every sibling, unstaffed
  destinations, stale choices, competing claims and tracking-only ancestors.
- Backend tests retain forged-hierarchy, stale-write, self-approval, effective-date
  and unchanged-comparison coverage.
- Security tests cover name normalisation and spoofing controls, future scheduled
  changes, approval digest mismatch and PostgreSQL lifecycle guards.
